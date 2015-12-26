__all__ = [
    'Http2Protocol',
]

import asyncio
import logging

from .http2 import Session


LOG = logging.getLogger(__name__)


class Http2Protocol(asyncio.Protocol):

    def __init__(self, handler_factory):
        super().__init__()
        self.handler_factory = handler_factory

    def connection_made(self, transport):
        if LOG.isEnabledFor(logging.DEBUG):
            peername = transport.get_extra_info('peername')
            LOG.debug('accept %s:%d', peername[0], peername[1])
        self.session = Session(transport, self.handler_factory())

    def data_received(self, data):
        self.session.data_received(data)

    def connection_lost(self, exc):
        LOG.debug('close connection', exc_info=bool(exc))
        self.session.close()
