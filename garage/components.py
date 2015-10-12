"""Initialize modules with 1- or 2- stages of startup.

The first startup is the normal, global startup object.  It is called
before main(), which will parse command-line arguments and it will
resolve MAIN and ARGS.  Its dependency graph is:

  PARSER ---> PARSE --+--> ARGS
                      |
              ARGV ---+

  MAIN

The second startup is component_startup.  You may use the second stage
startup to initialize "heavy" objects such as database connection.

NOTE: 'fqname' stands for 'fully-qualified name'.
"""

__all__ = [
    'ARGS',
    'EXIT_STACK',
    'MAIN',
    'PARSE',
    'PARSER',
    'Component',
    'bind',
    'fqname',
    'main',
    'make_fqname_tuple',
    'vars_as_namespace',
]

import functools
import types
from collections import namedtuple

from startup import startup as startup_

from garage import asserts
from garage.collections import DictAsAttrs


def fqname(module_name, name):
    return '%s:%s' % (module_name, name)


def _is_fqname(name):
    return ':' in name


def _get_name(maybe_fqname):
    return maybe_fqname[maybe_fqname.rfind(':')+1:]


ARGS = fqname(__name__, 'args')
ARGV = fqname(__name__, 'argv')
EXIT_STACK = fqname(__name__, 'exit_stack')
MAIN = fqname(__name__, 'main')
PARSE = fqname(__name__, 'parse')
PARSER = fqname(__name__, 'parser')


def make_fqname_tuple(module_name, *maybe_fqnames):
    if not maybe_fqnames:
        return ()
    names = [_get_name(name) for name in maybe_fqnames]
    return namedtuple('fqnames', names)(*(
        name if _is_fqname(name) else fqname(module_name, name)
        for name in maybe_fqnames
    ))


class Component:

    require = ()

    provide = None

    def add_arguments(self, parser):
        asserts.fail()

    def check_arguments(self, parser, args):
        asserts.fail()

    def make(self, require):
        asserts.fail()


def bind(component, startup=startup_, component_startup=None, parser_=PARSER):
    component_startup = component_startup or startup

    if _is_method_overridden(component, Component, 'add_arguments'):
        @functools.wraps(component.add_arguments)
        def add_arguments(parser):
            return component.add_arguments(parser)
        startup.add_func(add_arguments, {'parser': parser_, 'return': PARSE})

    if _is_method_overridden(component, Component, 'check_arguments'):
        @functools.wraps(component.check_arguments)
        def check_arguments(parser, args):
            return component.check_arguments(parser, args)
        startup.add_func(check_arguments, {'parser': PARSER, 'args': ARGS})

    if _is_method_overridden(component, Component, 'make'):
        provide = component.provide
        if isinstance(provide, tuple) and len(provide) == 1:
            provide = provide[0]
        annotations = {'return': provide}

        require = component.require
        if isinstance(require, str):
            require = (require,)
        for fqname_ in require:
            asserts.precond(_is_fqname(fqname_))
            name = _get_name(fqname_)
            asserts.precond(name not in annotations)
            annotations[name] = fqname_

        @functools.wraps(component.make)
        def make(**require):
            return component.make(DictAsAttrs(require))
        component_startup.add_func(make, annotations)


def _is_method_overridden(obj, base_cls, method_name):
    if not hasattr(obj, method_name):
        return False
    base_func = getattr(base_cls, method_name)
    method = getattr(obj, method_name)
    func = method.__func__ if isinstance(method, types.MethodType) else method
    return func is not base_func


def vars_as_namespace(varz):
    return DictAsAttrs({
        _get_name(fqname): value for fqname, value in varz.items()
    })


def parse_argv(parser: PARSER, argv: ARGV, _: PARSE) -> ARGS:
    return parser.parse_args(argv[1:])


def main(argv, startup=startup_, component_startup=None):
    startup.set(ARGV, argv)
    startup(parse_argv)
    varz = startup.call()
    if component_startup:
        for name, value in varz.items():
            component_startup.set(name, value)
    return varz[MAIN](varz[ARGS])
