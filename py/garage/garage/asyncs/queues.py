"""Closable queues."""

__all__ = [
    'Closed',
    'Empty',
    'Full',
    'Queue',
    'ZeroQueue',
]

import asyncio
import collections

from garage import asserts


class Closed(Exception):
    """Exception raised at put() when the queue is closed, or at get()
       when the queue is empty and closed.
    """
    pass


class Empty(Exception):
    """Exception raised at get(block=False) when queue is empty but not
       closed.
    """
    pass


class Full(Exception):
    """Exception raised at put(block=False) when queue is full."""
    pass


class QueueBase:

    def __init__(self, capacity=0, *, loop=None):
        self._capacity = capacity
        self._closed = asyncio.Event(loop=loop)
        # Use Event rather than Condition so that close() could be
        # non-async.
        self._has_item = asyncio.Event(loop=loop)
        self._has_vacancy = asyncio.Event(loop=loop)
        self._has_vacancy.set()
        # Call subclass method last.
        self._queue = self._make(self._capacity)

    def _make(self, capacity):
        raise NotImplementedError

    def _get(self):
        raise NotImplementedError

    def _put(self, item):
        raise NotImplementedError

    def __bool__(self):
        return bool(self._queue)

    def __len__(self):
        return len(self._queue)

    def is_empty(self):
        return not self._queue

    def is_full(self):
        return self._capacity > 0 and len(self._queue) >= self._capacity

    def is_closed(self):
        return self._closed.is_set()

    async def until_closed(self, raises=Closed):
        await self._closed.wait()
        if raises:
            raise raises

    def close(self, graceful=True):
        if self.is_closed():
            return []
        if graceful:
            items = []
        else:  # Drain the queue.
            items, self._queue = list(self._queue), ()
        self._closed.set()
        # Wake up all waiters.
        self._has_item.set()
        self._has_vacancy.set()
        return items

    async def put(self, item):
        while True:
            if self.is_closed():
                raise Closed
            if not self.is_full():
                break
            asserts.precond(not self._has_vacancy.is_set())
            await self._has_vacancy.wait()
        self.put_nowait(item)

    def put_nowait(self, item):
        """Non-blocking version of put()."""
        if self.is_closed():
            raise Closed
        if self.is_full():
            raise Full
        asserts.postcond(self._has_vacancy.is_set())
        self._put(item)
        self._has_item.set()
        if self.is_full():
            self._has_vacancy.clear()

    async def get(self):
        while self.is_empty():
            if self.is_closed():
                raise Closed
            asserts.precond(not self._has_item.is_set())
            await self._has_item.wait()
        return self.get_nowait()

    def get_nowait(self):
        """Non-blocking version of get()."""
        if self.is_empty():
            if self.is_closed():
                raise Closed
            raise Empty
        asserts.postcond(self._has_item.is_set())
        item = self._get()
        self._has_vacancy.set()
        if self.is_empty():
            self._has_item.clear()
        return item


class Queue(QueueBase):

    def _make(self, capacity):
        return collections.deque()

    def _get(self):
        return self._queue.popleft()

    def _put(self, item):
        self._queue.append(item)


class ZeroQueue:
    """A queue with zero capacity."""

    def __init__(self, *, loop=None):
        self._closed = asyncio.Event(loop=loop)

    def __bool__(self):
        return False

    def __len__(self):
        return 0

    def is_empty(self):
        return True

    def is_full(self):
        return True

    def is_closed(self):
        return self._closed.is_set()

    async def until_closed(self, raises=Closed):
        await self._closed.wait()
        if raises:
            raise raises

    def close(self, graceful=True):
        self._closed.set()
        return []

    async def put(self, item):
        if self.is_closed():
            raise Closed
        await self.until_closed()

    def put_nowait(self, item):
        if self.is_closed():
            raise Closed
        else:
            raise Full

    async def get(self):
        if self.is_closed():
            raise Closed
        await self.until_closed()

    def get_nowait(self):
        if self.is_closed():
            raise Closed
        else:
            raise Empty
