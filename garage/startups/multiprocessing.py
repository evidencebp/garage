__all__ = [
    'Python2Component',
]

from garage import components
from garage import multiprocessing


class Python2Component(components.Component):

    require = (components.ARGS, components.EXIT_STACK)

    provide = components.make_fqname_tuple(__name__, 'python2')

    def add_arguments(self, parser):
        group = parser.add_argument_group(multiprocessing.__name__)
        group.add_argument(
            '--python2', default='python2',
            help="""set path or command name of python2 executable""")

    def make(self, require):
        args, exit_stack = require.args, require.exit_stack
        return exit_stack.enter_context(multiprocessing.python(args.python2))
