import unittest

from startup import Startup

from garage.components import (
    Component,
    bind,
    make_fqname_tuple,
    _get_name,
    _is_method_overridden,
)


class ComponentsTest(unittest.TestCase):

    def test_get_name(self):
        self.assertEqual('hello', _get_name('hello'))
        self.assertEqual('hello', _get_name('a.b.c.d:hello'))

    def test_make_fqname_tuple(self):
        self.assertTupleEqual((), make_fqname_tuple('a.b.c'))
        fqnames = make_fqname_tuple('a.b.c', 'x', 'y', 'd.e.f:z')
        self.assertTupleEqual(('a.b.c:x', 'a.b.c:y', 'd.e.f:z'), fqnames)
        self.assertEqual('a.b.c:x', fqnames.x)
        self.assertEqual('a.b.c:y', fqnames.y)
        self.assertEqual('d.e.f:z', fqnames.z)

    def test_is_method_overridden(self):
        class Base:
            def meth1(self): pass
            def meth2(self): pass

        class Ext(Base):
            def meth1(self): pass
        self.assertTrue(_is_method_overridden(Ext, Base, 'meth1'))
        self.assertFalse(_is_method_overridden(Ext, Base, 'meth2'))
        self.assertTrue(_is_method_overridden(Ext(), Base, 'meth1'))
        self.assertFalse(_is_method_overridden(Ext(), Base, 'meth2'))

        class Ext(Base):
            @staticmethod
            def meth1(): pass
            @classmethod
            def meth2(cls): pass
        self.assertTrue(_is_method_overridden(Ext, Base, 'meth1'))
        self.assertTrue(_is_method_overridden(Ext, Base, 'meth2'))
        self.assertTrue(_is_method_overridden(Ext(), Base, 'meth1'))
        self.assertTrue(_is_method_overridden(Ext(), Base, 'meth2'))

    def test_empty_component(self):
        startup = Startup()
        bind(Component(), startup)
        self.assertDictEqual({}, startup.call())

        class A(Component): pass
        startup = Startup()
        bind(A(), startup)
        bind(A, startup)
        self.assertDictEqual({}, startup.call())

    def test_component(self):
        class A(Component):
            provide = ':A'
            def make(self, require):
                return 'a'

        class B(Component):
            require = ':A'
            provide = ':B'
            def make(self, require):
                return require.A

        startup = Startup()
        bind(A(), startup)
        bind(B(), startup)
        self.assertDictEqual({':A': 'a', ':B': 'a'}, startup.call())


if __name__ == '__main__':
    unittest.main()
