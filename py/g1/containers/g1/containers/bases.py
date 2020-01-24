__all__ = [
    'cmd_init',
    'get_repo_path',
    # Command-line arguments.
    'grace_period_arguments',
    'make_grace_period_kwargs',
    # Extension to Path object.
    'delete_file',
    'is_empty_dir',
    'lexists',
    # App-specific helpers.
    'assert_group_exist',
    'assert_program_exist',
    'assert_root_privilege',
    'check_program_exist',
    'chown_app',
    'chown_root',
    'make_dir',
    'rsync_copy',
    'setup_file',
    # File lock.
    'FileLock',
    'NotLocked',
    'acquiring_exclusive',
    'acquiring_shared',
    'try_acquire_exclusive',
    'is_locked_by_other',
]

import contextlib
import errno
import fcntl
import grp
import logging
import os
import shutil
from pathlib import Path

from g1 import scripts
from g1.apps import parameters
from g1.bases import argparses
from g1.bases import datetimes
from g1.bases.assertions import ASSERT

LOG = logging.getLogger(__name__)

PARAMS = parameters.define(
    'g1.containers',
    parameters.Namespace(
        repository=parameters.Parameter(
            '/var/lib/g1/containers',
            doc='path to the repository directory',
            type=str,
        ),
        application_group=parameters.Parameter(
            'plumber',
            doc='set application group',
            type=str,
        ),
        use_root_privilege=parameters.Parameter(
            True,
            doc='whether to check the process has root privilege '
            '(you may set this to false while testing)',
            type=bool,
        ),
        xar_runner_script_directory=parameters.Parameter(
            '/usr/local/bin',
            doc='path to the xar runner script directory',
            type=str,
        ),
    ),
)

REPO_LAYOUT_VERSION = 'v1'


def cmd_init():
    """Initialize the repository."""
    assert_group_exist(PARAMS.application_group.get())
    # For rsync_copy.
    check_program_exist('rsync')
    assert_root_privilege()
    make_dir(get_repo_path(), 0o750, chown_app, parents=True)


def get_repo_path():
    return (Path(PARAMS.repository.get()) / REPO_LAYOUT_VERSION).absolute()


#
# Command-line arguments.
#

grace_period_arguments = argparses.argument(
    '--grace-period',
    type=argparses.parse_timedelta,
    default='24h',
    help='set grace period (default to %(default)s)',
)


def make_grace_period_kwargs(args):
    return {'expiration': datetimes.utcnow() - args.grace_period}


#
# Extension to Path object.
#


def is_empty_dir(path):
    """True on empty directory."""
    try:
        next(path.iterdir())
    except StopIteration:
        return True
    except (FileNotFoundError, NotADirectoryError):
        return False
    else:
        return False


def lexists(path):
    """True if a file or symlink exists.

    ``lexists`` differs from ``Path.exists`` when path points to a
    broken but existent symlink: The former returns true but the latter
    returns false.
    """
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    else:
        return True


def delete_file(path):
    """Delete a file, handling symlink to directory correctly."""
    if not lexists(path):
        pass
    elif not path.is_dir() or path.is_symlink():
        path.unlink()
    else:
        shutil.rmtree(path)


#
# App-specific helpers.
#


def assert_program_exist(program):
    # Assume it's unit testing if not use_root_privilege.
    if PARAMS.use_root_privilege.get():
        ASSERT.not_none(shutil.which(program))


def check_program_exist(program):
    # Assume it's unit testing if not use_root_privilege.
    if PARAMS.use_root_privilege.get():
        if not shutil.which(program):
            LOG.warning(
                'program %s does not exist; certain features are unavailable',
                program
            )


def assert_group_exist(name):
    # Assume it's unit testing if not use_root_privilege.
    if PARAMS.use_root_privilege.get():
        try:
            grp.getgrnam(name)
        except KeyError:
            raise AssertionError('expect group: %s' % name) from None


def assert_root_privilege():
    if PARAMS.use_root_privilege.get():
        ASSERT.equal(os.geteuid(), 0)


def chown_app(path):
    """Change owner to root and group to the application group."""
    if PARAMS.use_root_privilege.get():
        shutil.chown(
            path,
            'root',
            ASSERT.true(PARAMS.application_group.get()),
        )


def chown_root(path):
    """Change owner and group to root."""
    if PARAMS.use_root_privilege.get():
        shutil.chown(path, 'root', 'root')


def make_dir(path, mode, chown, *, parents=False, exist_ok=True):
    LOG.info('create directory: %s', path)
    path.mkdir(mode=mode, parents=parents, exist_ok=exist_ok)
    chown(path)


def setup_file(path, mode, chown):
    path.chmod(mode)
    chown(path)


def rsync_copy(src_path, dst_path, rsync_args=()):
    # We do NOT use ``shutil.copytree`` because shutil's file copy
    # functions in general do not preserve the file owner/group.
    LOG.info('copy: %s -> %s', src_path, dst_path)
    scripts.run([
        'rsync',
        '--archive',
        *rsync_args,
        # Trailing slash is an rsync trick.
        '%s/' % src_path,
        dst_path,
    ])


#
# File lock.
#


class NotLocked(Exception):
    """Raise when file lock cannot be acquired."""


class FileLock:

    def __init__(self, path, *, close_on_exec=True):
        fd = os.open(path, os.O_RDONLY)
        try:
            # Actually, CPython's os.open always sets O_CLOEXEC.
            flags = fcntl.fcntl(fd, fcntl.F_GETFD)
            if close_on_exec:
                new_flags = flags | fcntl.FD_CLOEXEC
            else:
                new_flags = flags & ~fcntl.FD_CLOEXEC
            if new_flags != flags:
                fcntl.fcntl(fd, fcntl.F_SETFD, new_flags)
        except:
            os.close(fd)
            raise
        self._fd = fd

    def acquire_shared(self):
        self._acquire(fcntl.LOCK_SH)

    def acquire_exclusive(self):
        self._acquire(fcntl.LOCK_EX)

    def _acquire(self, operation):
        ASSERT.not_none(self._fd)
        # TODO: Should we add a retry here?
        try:
            fcntl.flock(self._fd, operation | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            if exc.errno != errno.EWOULDBLOCK:
                raise
            raise NotLocked from None

    def release(self):
        """Release file lock.

        It is safe to call release even if lock has not been acquired.
        """
        ASSERT.not_none(self._fd)
        fcntl.flock(self._fd, fcntl.LOCK_UN)

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None


@contextlib.contextmanager
def acquiring_shared(path):
    lock = FileLock(path)
    try:
        lock.acquire_shared()
        yield lock
    finally:
        lock.release()
        lock.close()


@contextlib.contextmanager
def acquiring_exclusive(path):
    lock = FileLock(path)
    try:
        lock.acquire_exclusive()
        yield lock
    finally:
        lock.release()
        lock.close()


def try_acquire_exclusive(path):
    lock = FileLock(path)
    try:
        lock.acquire_exclusive()
    except NotLocked:
        lock.close()
        return None
    else:
        return lock


def is_locked_by_other(path):
    lock = try_acquire_exclusive(path)
    if lock:
        lock.release()
        lock.close()
        return False
    else:
        return True
