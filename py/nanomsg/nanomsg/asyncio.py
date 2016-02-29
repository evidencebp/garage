__all__ = [
    'Socket',
]

import asyncio

from . import SocketBase
from . import errors
from .constants import AF_SP
from .constants import Error
from .constants import NN_DONTWAIT
from .errors import Closed


class Socket(SocketBase):

    def __init__(self, *, domain=AF_SP, protocol=None, socket_fd=None,
                 loop=None):
        super().__init__(domain=domain, protocol=protocol, socket_fd=socket_fd)

        self._loop = loop or asyncio.get_event_loop()

        sndfd = None
        try:
            sndfd = self.options.sndfd
        except errors.NanomsgError as err:
            if err.errno is not Error.ENOPROTOOPT:
                raise
        if sndfd is None:
            self._sndfd_ready = None
        else:
            self._sndfd_ready = asyncio.Event(loop=self._loop)
            self._loop.add_writer(sndfd, self._sndfd_ready.set)

        rcvfd = None
        try:
            rcvfd = self.options.rcvfd
        except errors.NanomsgError as err:
            if err.errno is not Error.ENOPROTOOPT:
                raise
        if rcvfd is None:
            self._rcvfd_ready = None
        else:
            self._rcvfd_ready = asyncio.Event(loop=self._loop)
            self._loop.add_reader(rcvfd, self._rcvfd_ready.set)

    def close(self):
        if self.fd is None:
            return
        if self._sndfd_ready is not None:
            self._loop.remove_writer(self.options.sndfd)
            self._sndfd_ready.set()
        if self._rcvfd_ready is not None:
            self._loop.remove_reader(self.options.rcvfd)
            self._rcvfd_ready.set()
        super().close()

    async def __aenter__(self):
        return super().__enter__()

    async def __aexit__(self, *exc_info):
        return super().__exit__(*exc_info)  # XXX: Would this block?

    async def send(self, message, size=None, flags=0):
        return await self._async_tx(
            self._sndfd_ready, self._blocking_send, message, size, flags)

    async def recv(self, message=None, size=None, flags=0):
        return await self._async_tx(
            self._rcvfd_ready, self._blocking_recv, message, size, flags)

    async def _async_tx(self, ready, tx, message, size, flags):
        if self.fd is None or ready is None:
            raise AssertionError
        flags |= NN_DONTWAIT
        while True:
            await ready.wait()
            ready.clear()
            if self.fd is None:
                raise Closed
            try:
                return tx(message, size, flags)
            except errors.NanomsgEagain:
                pass
