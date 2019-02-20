from setuptools import setup

setup(
    name='g1.asyncs.servers',
    packages=[
        'g1.asyncs.servers',
    ],
    install_requires=[
        'g1.asyncs.bases',
    ],
    extras_require={
        'parts': [
            'g1.apps[asyncs]',
        ],
    },
    zip_safe=False,
)
