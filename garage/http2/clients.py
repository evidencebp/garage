"""A thin layer on top of the requests package that provides niceties
such as retry policy, rate limit, and more logging.
"""

__all__ = [
    'Client',
    'ForwardingClient',
    'Request',
    'Response',
]

import time
import logging

import requests

from garage.http2 import policies


LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


def _make_method(method):
    def http_method(self, uri, **kwargs):
        return self.send(Request(method, uri, **kwargs))
    return http_method


class ClientMixin:

    get = _make_method('GET')
    head = _make_method('HEAD')
    post = _make_method('POST')
    put = _make_method('PUT')


class Client(ClientMixin):

    def __init__(self, *,
                 rate_limit=None,
                 retry_policy=None,
                 _session=None,
                 _sleep=time.sleep):
        self._session = _session or requests.Session()
        self._rate_limit = rate_limit or policies.Unlimited()
        self._retry_policy = retry_policy or policies.NoRetry()
        self._sleep = _sleep

    @property
    def headers(self):
        return self._session.headers

    def send(self, request):
        rreq = request.make_request()
        retry = self._retry_policy()
        retry_count = 0
        while True:
            try:
                return self._send(request, rreq, retry_count)
            except BaseException:
                backoff = next(retry, None)
                if backoff is None:
                    raise
            self._sleep(backoff)
            retry_count += 1

    def _send(self, request, rreq, retry_count):
        try:
            with self._rate_limit:
                if retry_count:
                    LOG.warning('Retry %d times of %s %s',
                                retry_count, request.method, request.uri)
                if LOG.isEnabledFor(logging.DEBUG):
                    for name, value in rreq.headers.items():
                        LOG.debug('<<< %s: %s', name, value)
                rrep = self._session.send(rreq)
                if LOG.isEnabledFor(logging.DEBUG):
                    for name, value in rrep.headers.items():
                        LOG.debug('>>> %s: %s', name, value)
                rrep.raise_for_status()
                return Response(rrep)
        except requests.RequestException as exc:
            if exc.response is not None:
                status_code = exc.response.status_code
            else:
                status_code = '?'
            LOG.warning('HTTP error with status code %s when %s %s',
                        status_code, request.method, request.uri,
                        exc_info=True)
            raise
        except BaseException:
            LOG.warning('Generic error when %s %s',
                        request.method, request.uri, exc_info=True)
            raise


class ForwardingClient(ClientMixin):
    """A client that forwards requests to the underlying client."""

    def __init__(self, client):
        self.client = client

    @property
    def headers(self):
        return self.client.headers

    def send(self, request):
        request = self.on_request(request)
        response = self.client.send(request)
        response = self.on_response(request, response)
        return response

    def on_request(self, request):
        """Hook for modifying request."""
        return request

    def on_response(self, _, response):
        """Hook for modifying response."""
        return response


class Request:
    """A thin wrapper of requests.Request."""

    def __init__(self, method, uri):
        self.method = method
        self.uri = uri

    def make_request(self):
        return requests.Request(self.method, self.uri)


class Response:
    """A thin wrapper of requests.Response."""

    def __init__(self, response):
        object.__setattr__(self, '_response', response)

    def __getattr__(self, name):
        return getattr(self._response, name)
