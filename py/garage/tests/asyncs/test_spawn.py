import unittest

import curio

from garage import asyncs
from garage.asyncs.utils import synchronous


class SpawnTest(unittest.TestCase):

    @synchronous
    async def test_spawn(self):

        async def coro():
            try:
                await curio.sleep(100)
            except Exception as e:
                self.fail('asyncs.TaskCancelled is not raised: %r' % e)

        task = await asyncs.spawn(coro())
        self.assertTrue(await task.cancel())
        with self.assertRaises(curio.TaskError):
            await task.join()
        self.assertEqual('CANCELLED', task.state)


if __name__ == '__main__':
    unittest.main()
