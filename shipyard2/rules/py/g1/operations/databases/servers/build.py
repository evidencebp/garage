import shipyard2.rules.pythons

shipyard2.rules.pythons.define_package(
    deps=[
        '//py/g1/asyncs/bases:build',
        '//py/g1/bases:build',
        '//py/g1/databases:build',
        '//py/g1/operations/databases/bases:build',
        '//third-party/sqlalchemy:build',
    ],
    extras=[
        (
            'apps',
            [
                '//py/g1/apps:build/asyncs',
                '//py/g1/asyncs/agents:build/parts',
                '//py/g1/asyncs/kernels:build',
                '//py/g1/operations/databases/servers:build/parts',
            ],
        ),
        (
            'parts',
            [
                '//py/g1/apps:build/asyncs',
                '//py/g1/asyncs/agents:build/parts',
                '//py/g1/asyncs/bases:build',
                '//py/g1/databases:build/parts',
                '//py/g1/messaging:build/parts/pubsub',
                '//py/g1/messaging:build/parts/servers',
                '//py/g1/messaging:build/pubsub',
                '//py/g1/messaging:build/reqrep',
                '//py/g1/operations/databases/bases:build/capnps',
            ],
        ),
    ],
)
