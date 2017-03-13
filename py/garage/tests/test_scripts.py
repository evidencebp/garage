import unittest

from pathlib import Path
import os
import subprocess
import threading

from garage import scripts


class ScriptsTest(unittest.TestCase):

    def test_ensure_path(self):
        self.assertEqual(Path('/a/b/c'), scripts.ensure_path(Path('/a/b/c')))
        self.assertEqual(Path('/a/b/c'), scripts.ensure_path('/a/b/c'))
        self.assertIsNone(scripts.ensure_path(None))

    def test_ensure_str(self):
        self.assertEqual('', scripts.ensure_str(''))
        self.assertEqual('x', scripts.ensure_str('x'))
        self.assertEqual('x', scripts.ensure_str(Path('x')))
        self.assertIsNone(scripts.ensure_str(None))

    def test_make_command(self):
        self.assertEqual(['ls'], scripts.make_command(['ls']))
        with scripts.using_sudo():
            self.assertEqual(['sudo', 'ls'], scripts.make_command(['ls']))
            with scripts.using_sudo(False):
                self.assertEqual(['ls'], scripts.make_command(['ls']))

    def test_context(self):

        barrier = threading.Barrier(2)
        data = set()

        def f(path):
            with scripts.directory(path):
                data.add(scripts._get_context()[scripts.DIRECTORY])
                barrier.wait()

        with scripts.directory('p0'):
            t1 = threading.Thread(target=f, args=('p1',))
            t1.start()
            t2 = threading.Thread(target=f, args=('p2',))
            t2.start()
            t1.join()
            t2.join()

        self.assertEqual({Path('p1'), Path('p2')}, data)

    def test_execute(self):

        self.assertEqual(
            b'hello\n',
            scripts.execute(['echo', 'hello'], capture_stdout=True).stdout,
        )

        with scripts.dry_run():
            self.assertEqual(
                b'',
                scripts.execute(['echo', 'hello'], capture_stdout=True).stdout,
            )

        with scripts.redirecting(stdout=subprocess.PIPE):
            self.assertEqual(
                b'hello\n',
                scripts.execute(['echo', 'hello']).stdout,
            )

        with scripts.redirecting(stdout=subprocess.DEVNULL):
            self.assertEqual(
                None,
                scripts.execute(['echo', 'hello']).stdout,
            )

    def test_pipeline(self):

        result = []

        def process():
            input_fd = scripts.get_stdin()
            output_fd = scripts.get_stdout()
            while True:
                data = os.read(input_fd, 32)
                result.append(data)
                if not data:
                    break
                os.write(output_fd, data)

        cmds = [
            lambda: scripts.execute(['echo', 'hello']),
            process,
            lambda: scripts.execute(['cat']),
        ]
        read_fd, write_fd = os.pipe()
        try:
            scripts.pipeline(cmds, pipe_output=write_fd)
            # os.read may return less than we ask...
            self.assertEqual(b'hello\n', os.read(read_fd, 32))
        finally:
            os.close(read_fd)
            # pipeline() closes write_fd

        self.assertEqual(b'hello\n', b''.join(result))

    def test_pipeline_failure(self):

        def process():
            raise Exception

        with self.assertRaisesRegex(RuntimeError, 'pipeline fail'):
            scripts.pipeline([process])

    def test_pipeline_preserve_context(self):

        result = []

        def process():
            result.append(scripts.is_dry_run())

        scripts.pipeline([process])

        with scripts.dry_run():
            scripts.pipeline([process])

            with scripts.dry_run(False):
                scripts.pipeline([process])

        self.assertEqual([False, True, False], result)

    def test_gzip(self):

        def generate_data():
            output_fd = scripts.get_stdout()
            # os.write may write less than we ask...
            os.write(output_fd, b'hello')

        data_out = os.pipe()
        try:
            scripts.pipeline(
                [generate_data, scripts.gzip, scripts.gunzip],
                pipe_output=data_out[1],
            )
            # os.read may read less than we ask...
            self.assertEqual(b'hello', os.read(data_out[0], 32))
        finally:
            os.close(data_out[0])


if __name__ == '__main__':
    unittest.main()
