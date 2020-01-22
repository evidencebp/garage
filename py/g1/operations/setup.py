from setuptools import setup

from g1.devtools import buildtools

setup(
    name='g1.operations',
    entry_points={
        'console_scripts': [
            'ops = g1.operations.apps:run [apps]',
        ],
    },
    # For now, ops tool only depends on first-party, pure-Python
    # libraries (thus zipapp-able), but this might not be held in the
    # future (thus not zipapp-able) and it will be turned into a XAR.
    cmdclass={
        'bdist_zipapp':
        buildtools.make_bdist_zipapp(main='g1.operations.apps:run'),
    },
    packages=[
        'g1.operations',
    ],
    install_requires=[
        'g1.bases',
        'g1.containers',
    ],
    extras_require={
        'apps': [
            'g1.apps',
            'g1.containers[scripts]',
            'g1.scripts[parts]',
        ],
    },
    zip_safe=False,
)
