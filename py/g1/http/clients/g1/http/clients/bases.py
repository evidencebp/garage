__all__ = [
    'BaseSession',
    'Request',
    'Response',
    'Sender',
]

import functools
import itertools
import json
import logging

import lxml.etree
import requests
import requests.cookies
import urllib3.exceptions

from g1.asyncs.bases import adapters
from g1.asyncs.bases import tasks
from g1.asyncs.bases import timers
from g1.bases import classes
from g1.bases import collections as g1_collections
from g1.bases.assertions import ASSERT
from g1.threads import executors

from . import policies

LOG = logging.getLogger(__name__)


class Sender:
    """Request sender with local cache, rate limit, and retry."""

    def __init__(self, send, *, cache_size=8, rate_limit=None, retry=None):
        self._send = send
        self._cache = g1_collections.LruCache(cache_size)
        self._unbounded_cache = {}
        self._rate_limit = rate_limit or policies.unlimited
        self._retry = retry or policies.no_retry

    async def __call__(self, request, **kwargs):
        """Send a request and return a response.

        If argument ``cache_key`` is not ``None``, session will check
        its cache before sending the request.  For now, we don't support
        setting ``cache_key`` in ``request``.

        ``sticky_key`` is similar to ``cache_key`` except that it refers
        to an unbounded cache (thus the name "sticky").

        If argument ``cache_revalidate`` is evaludated to true, session
        will revalidate the cache entry.
        """
        cache_key = kwargs.pop('cache_key', None)
        sticky_key = kwargs.pop('sticky_key', None)
        cache_revalidate = kwargs.pop('cache_revalidate', None)
        if cache_key is not None and sticky_key is not None:
            raise AssertionError(
                'expect at most one: cache_key=%r, sticky_key=%r' %
                (cache_key, sticky_key)
            )
        if cache_key is not None:
            return await self._try_cache(
                self._cache,
                cache_key,
                cache_revalidate,
                request,
                kwargs,
            )
        if sticky_key is not None:
            return await self._try_cache(
                self._unbounded_cache,
                sticky_key,
                cache_revalidate,
                request,
                kwargs,
            )

        for retry_count in itertools.count():
            await self._rate_limit()
            if retry_count:
                LOG.warning('retry %d times: %r', retry_count, request)
            try:
                return await self._send(request, **kwargs)
            except (
                requests.RequestException,
                urllib3.exceptions.HTTPError,
            ) as exc:
                backoff = self._retry(retry_count)
                if backoff is None:
                    raise
                # NOTE: requests.Response defines __bool__ that returns
                # to true when status code is less than 400.  This is
                # certainly surprising sometimes.  Anyway, you have to
                # explicitly check `is None` here.
                if getattr(exc, 'response', None) is not None:
                    status_code = exc.response.status_code
                    # It does not seem to make sense to retry on 4xx
                    # errors since our request was explicitly rejected
                    # by the server.
                    if 400 <= status_code < 500:
                        raise
                else:
                    status_code = None
                LOG.warning(
                    'http error: status_code=%s, request=%r, exc=%r',
                    status_code,
                    request,
                    exc,
                )
                await timers.sleep(backoff)
        ASSERT.unreachable('retry loop should not break')

    async def _try_cache(self, cache, key, revalidate, request, kwargs):
        task = cache.get(key)
        if task is None:
            task = cache[key] = tasks.spawn(self(request, **kwargs))
            result = 'miss'
        elif revalidate:
            task = cache[key] = tasks.spawn(self(request, **kwargs))
            result = 'revalidate'
        else:
            result = 'hit'
        LOG.debug(
            'send: cache %s: key=%r, %r, kwargs=%r', \
            result, key, request, kwargs,
        )
        # Here is a risk that, if all task waiting for this task get
        # cancelled before this task completes, this task might not
        # be joined, but this risk is probably too small.
        return await task.get_result()


class BaseSession:
    """Base session.

    All this does is backing an HTTP session with an executor; this does
    not provide rate limit nor retry.  You use this as a building block
    for higher level session types.
    """

    def __init__(self, executor=None):
        # If you do not provide an executor, I will just make one for
        # myself, but to save you the effort to shut down the executor,
        # I will also make it daemonic.  This is mostly fine since if
        # the process is exiting, you probably do not care much about
        # unfinished HTTP requests in the executor (if it is not fine,
        # you may always provide an executor to me, and properly shut it
        # down on process exit).
        self._executor = executor or executors.Executor(daemon=True)
        self._session = requests.Session()

    @property
    def headers(self):
        return self._session.headers

    @property
    def cookies(self):
        return self._session.cookies

    def update_cookies(self, cookie_dict):
        """Update cookies with a dict-like object."""
        requests.cookies.cookiejar_from_dict(
            cookie_dict, self._session.cookies
        )

    async def send(self, request, **kwargs):
        """Send an HTTP request and return a response.

        If argument ``priority`` is not ``None``, the request is sent
        with priority (this requires ``PriorityExecutor``).  For now, we
        do not support setting ``priority`` in ``request``.
        """
        priority = kwargs.pop('priority', None)
        if priority is None:
            future = self._executor.submit(
                self.send_blocking, request, **kwargs
            )
        else:
            LOG.debug(
                'send: priority=%r, %r, kwargs=%r', priority, request, kwargs
            )
            future = self._executor.submit_with_priority(
                priority, self.send_blocking, request, **kwargs
            )
        return await adapters.FutureAdapter(future).get_result()

    def send_blocking(self, request, **kwargs):
        """Send a request in a blocking manner.

        If ``stream`` is set to true, we will return the original
        response object, and will NOT copy-then-close it to our response
        class.  In this case, the caller is responsible for closing the
        response object.

        This does not implement rate limit nor retry.
        """
        LOG.debug('send: %r, kwargs=%r', request, kwargs)

        # ``requests.Session.get`` and friends do a little more than
        # ``requests.Session.request``; so let's use the former.
        method = getattr(self._session, request.method.lower())

        # ``kwargs`` may overwrite ``request._kwargs``.
        final_kwargs = request._kwargs.copy()
        final_kwargs.update(kwargs)

        source = method(request.url, **final_kwargs)
        stream = final_kwargs.get('stream')
        if stream:
            response = source
        else:
            try:
                response = Response(source)
            finally:
                _close_response_recursively(source)

        try:
            response.raise_for_status()
        except Exception:
            # On error, close the original response for the caller since
            # the caller usually forgets to do this.
            if stream:
                # Consume the content because we are going to close it.
                response.content  # pylint: disable=pointless-statement
                response.close()
            raise

        return response


def _close_response_recursively(response):
    response.close()
    for r in response.history:
        _close_response_recursively(r)


class Request:

    def __init__(self, method, url, **kwargs):
        self.method = method
        self.url = url
        self._kwargs = kwargs

    __repr__ = classes.make_repr(
        '{method} {self.url} kwargs={self._kwargs!r}',
        method=lambda self: self.method.upper(),
    )

    @property
    def headers(self):
        return self._kwargs.setdefault('headers', {})

    def copy(self):
        return Request(self.method, self.url, **self._kwargs)


class Response:
    """HTTP response.

    This class provides an interface that is  mostly compatible with
    ``requests`` Response class.

    We do this because it is suspected that when a ``requests`` Response
    object is not explicitly closed (as doc says it should not have to),
    it could somehow cause Python interpreter not returning heap space
    to the kernel.  Although we are unable to reproduce this issue, we
    think it might be worthwhile to try this "fix" anyway.
    """

    def __init__(self, source):
        """Make a "copy" from a ``requests`` Response object.

        Note that this consumes the content of the ``source`` object,
        which forces ``source`` to read the whole response body from the
        server (and so we do not need to do this in the Sender class).
        """
        # Force reading.
        self.content = source.content

        self.status_code = source.status_code
        self.headers = source.headers
        self.url = source.url
        self.history = list(map(Response, source.history))
        self.encoding = source.encoding
        self.reason = source.reason
        self.cookies = source.cookies
        self.elapsed = source.elapsed
        # We do not copy source.request for now.

    __repr__ = classes.make_repr(
        'status_code={self.status_code} url={self.url}',
    )

    def raise_for_status(self):
        if not 400 <= self.status_code < 600:
            return
        if isinstance(self.reason, bytes):
            # Try utf-8 first because some servers choose to localize
            # their reason strings.  If the string is not utf-8, fall
            # back to iso-8859-1.
            try:
                reason = self.reason.decode('utf-8')
            except UnicodeDecodeError:
                reason = self.reason.decode('iso-8859-1')
        else:
            reason = self.reason
        raise requests.HTTPError(
            '%s %s error: %s %s' % (
                self.status_code,
                'client' if 400 <= self.status_code < 500 else 'server',
                reason,
                self.url,
            ),
            response=self,
        )

    @classes.memorizing_property
    def text(self):
        # NOTE: Unlike ``requests``, we do NOT fall back to
        # auto-detected encoding.
        return self.content.decode(ASSERT.not_none(self.encoding))

    def json(self, **kwargs):
        """Parse response as a JSON document."""
        return json.loads(self.content, **kwargs)

    #
    # Interface that ``requests.Response`` does not provide.
    #

    def html(self, encoding=None, errors=None):
        """Parse response as an HTML document.

        Caller may pass ``encoding`` and ``errors`` to instructing us
        how to decode response content.  This is useful because lxml's
        default is to **silently** skip the rest of the document when
        there is any encoding error in the middle.

        lxml's strict-but-silent policy is counterproductive because web
        is full of malformed documents, and it should either be lenient
        about the error, or raise it to the caller, not a mix of both as
        it is right now.
        """
        if encoding and errors:
            string = self.content.decode(encoding=encoding, errors=errors)
            parser = _get_html_parser(None)
        else:
            ASSERT.none(errors)
            string = self.content
            parser = _get_html_parser(
                encoding or ASSERT.not_none(self.encoding)
            )
        return lxml.etree.fromstring(string, parser)

    def xml(self):
        """Parse response as an XML document."""
        return lxml.etree.fromstring(self.content, _XML_PARSER)


@functools.lru_cache(maxsize=8)
def _get_html_parser(encoding):
    return lxml.etree.HTMLParser(encoding=encoding)


_XML_PARSER = lxml.etree.XMLParser()
