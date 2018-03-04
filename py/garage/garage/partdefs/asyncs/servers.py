import functools

import curio

from garage import asyncs
from garage import parameters
from garage import parts
from garage.asyncs import servers


PARTS = parts.PartList(servers.__name__, [
    ('graceful_exit', parts.AUTO),
    ('server', parts.AUTO),
    ('serve', parts.AUTO),
])


PARAMS = parameters.get(
    servers.__name__, 'async servers')
PARAMS.grace_period = parameters.define(
    5, unit='second', doc='grace period for shutting down servers')


@parts.register_maker
def make_graceful_exit() -> PARTS.graceful_exit:
    return asyncs.Event()


@parts.register_maker
def make_serve(
        graceful_exit: PARTS.graceful_exit,
        server_coros: [PARTS.server],
    ) -> PARTS.serve:
    return functools.partial(
        servers.serve,
        graceful_exit=graceful_exit,
        grace_period=PARAMS.grace_period.get(),
        server_coros=server_coros,
    )


#
# A stock main function.
#
# NOTE: Do not decorate it with `@apps`, which creates an apps.App
# object, because it might be shared in multiple places, and if they all
# decorate it further, they will be modifying the same apps.App object.
def main(_, serve: PARTS.serve):
    return 0 if curio.run(serve()) else 1
