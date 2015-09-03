"""Initialize garage.http."""

__all__ = [
    'MAKE_CLIENT',
    'init',
]

import functools

from startup import startup

import garage.http
from garage.functools import run_once
from garage.http import clients
from garage.http import policies

import garage.startups
from garage.startups import ARGS, PARSE, PARSER


MAKE_CLIENT = __name__ + '#make_client'


HTTP_USER_AGENT = (
    'Mozilla/5.0 (X11; Linux x86_64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/40.0.2214.111 Safari/537.36'
)


def add_arguments(parser: PARSER) -> PARSE:
    group = parser.add_argument_group(garage.http.__name__)
    group.add_argument(
        '--http-user-agent', default=HTTP_USER_AGENT,
        help="""set http user agent""")
    group.add_argument(
        '--http-max-requests', type=int, default=0,
        help="""set max concurrent http requests or 0 for unlimited
                (default to %(default)s)
             """)
    group.add_argument(
        '--http-retry', type=int, default=0,
        help="""set number of http retries or 0 for no retries
                (default to %(default)s)
             """)


def configure(args: ARGS) -> MAKE_CLIENT:
    return functools.partial(
        make_client,
        args.http_user_agent,
        args.http_max_requests,
        args.http_retry,
    )


def make_client(
        http_user_agent,
        http_max_requests,
        http_retry):

    if http_max_requests > 0:
        rate_limit = policies.MaxConcurrentRequests(http_max_requests)
    else:
        rate_limit = policies.Unlimited()

    if http_retry > 0:
        retry_policy = policies.BinaryExponentialBackoff(http_retry)
    else:
        retry_policy = policies.NoRetry()

    client = clients.Client(
        rate_limit=rate_limit,
        retry_policy=retry_policy,
    )
    client.headers['User-Agent'] = http_user_agent

    return client


@run_once
def init():
    garage.startups.init()
    startup(add_arguments)
    startup(configure)
