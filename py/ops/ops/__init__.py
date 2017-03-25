from pathlib import Path
import logging

from garage import cli, scripts
from garage.components import ARGS

from .deps import deps
from .repos import Repo


logging.getLogger(__name__).addHandler(logging.NullHandler())


@cli.command('list', help='list allocated ports')
def list_ports(args: ARGS):
    """List ports allocated to deployed pods."""
    for port in Repo(args.root).get_ports():
        print('%s:%d %s %d' %
              (port.pod_name, port.pod_version, port.name, port.port))
    return 0


@cli.command(help='manage host ports')
@cli.sub_command_info('operation', 'operation on ports')
@cli.sub_command(list_ports)
def ports(args: ARGS):
    """Manage host ports allocated to pods."""
    return args.operation()


@cli.command('ops')
@cli.argument('--dry-run', action='store_true', help='do not execute commands')
@cli.argument(
    '--root', metavar='PATH', type=Path, default=Path('/var/lib/ops'),
    help='set root directory of repos (default %(default)s)'
)
@cli.sub_command_info('entity', 'system entity to be operated on')
@cli.sub_command(deps)
@cli.sub_command(ports)
def main(args: ARGS):
    """Operations tool."""
    with scripts.dry_run(args.dry_run):
        scripts.ensure_not_root()
        return args.entity()
