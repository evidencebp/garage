__all__ = [
    'SchemaLoader',
]

import functools
import logging

from g1.bases import classes
from g1.bases import labels
from g1.bases.assertions import ASSERT

from . import _capnp
# pylint: disable=c-extension-no-member

from . import bases

#
# TODO: We expose classes and methods as needed for now; so don't expect
# them to be comprehensive.
#

LOG = logging.getLogger(__name__)

# Annotation node id from capnp/c++.capnp.
CXX_NAMESPACE = 0xb9c6f99ebf805f2c
CXX_NAME = 0xf264a779fef191ce


class SchemaLoader:

    def __init__(self):
        self._loader = _capnp.SchemaLoader()
        # Caches for all kinds of schemas.
        self._files = None
        self._struct_schemas = None
        self._enum_schemas = None
        self._interface_schemas = None
        self._const_schemas = None
        self._annotations = None

    def _reset_caches(self):
        if self._files is None:
            return
        LOG.debug('invalidate schema caches')
        self._files = None
        self._struct_schemas = None
        self._enum_schemas = None
        self._interface_schemas = None
        self._const_schemas = None
        self._annotations = None

    def _get_cache(self, name):
        cache = getattr(self, name)
        if cache is None:
            self._load_caches()
            cache = ASSERT.not_none(getattr(self, name))
        return cache

    files = property(  # File schemas are special.
        functools.partial(_get_cache, name='_files'),
    )
    struct_schemas = property(
        functools.partial(_get_cache, name='_struct_schemas'),
    )
    enum_schemas = property(
        functools.partial(_get_cache, name='_enum_schemas'),
    )
    interface_schemas = property(
        functools.partial(_get_cache, name='_interface_schemas'),
    )
    const_schemas = property(
        functools.partial(_get_cache, name='_const_schemas'),
    )
    annotations = property(  # Annotation schemas are special.
        functools.partial(_get_cache, name='_annotations'),
    )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        loader, self._loader = self._loader, None
        loader._reset()

    def load(self, codegen_request_bytes):
        self._do_load(
            codegen_request_bytes,
            ASSERT.not_none(self._loader).load,
        )

    def load_once(self, codegen_request_bytes):
        self._do_load(
            codegen_request_bytes,
            ASSERT.not_none(self._loader).loadOnce,
        )

    def _do_load(self, codegen_request_bytes, load):
        reader = _capnp.FlatArrayMessageReader(codegen_request_bytes)
        try:
            codegen_request = reader.getRoot()
            for node in codegen_request.getNodes():
                load(node)
        finally:
            reader._reset()
        self._reset_caches()

    def _load_caches(self):
        ASSERT.not_none(self._loader)
        LOG.debug('build schema cache')

        id_to_schema = {
            schema.proto.id: schema
            for schema in map(Schema, self._loader.getAllLoaded())
        }

        files = {}
        struct_schemas = {}
        enum_schemas = {}
        interface_schemas = {}
        const_schemas = {}
        annotations = {}

        for schema in id_to_schema.values():

            if schema.proto.is_file():
                path = schema.proto.display_name
                LOG.debug('cache schema: %s', path)
                files[path] = schema
                continue

            label = labels.Label(
                self._get_module_path(schema, id_to_schema),
                self._get_object_path(schema, id_to_schema),
            )
            LOG.debug('cache schema: %s', label)

            if schema.proto.is_struct():
                struct_schemas[label] = schema.as_struct()

            elif schema.proto.is_enum():
                enum_schemas[label] = schema.as_enum()

            elif schema.proto.is_interface():
                interface_schemas[label] = schema.as_interface()

            elif schema.proto.is_const():
                const_schemas[label] = schema.as_const()

            elif schema.proto.is_annotation():
                annotations[label] = schema

            else:
                ASSERT.unreachable('unexpected schema kind: {}', schema)

        self._files = files
        self._struct_schemas = struct_schemas
        self._enum_schemas = enum_schemas
        self._interface_schemas = interface_schemas
        self._const_schemas = const_schemas
        self._annotations = annotations

    @staticmethod
    def _get_module_path(schema, id_to_schema):
        while schema and not schema.proto.is_file():
            schema = id_to_schema.get(schema.proto.scope_id)
        ASSERT.not_none(schema)
        for annotation in schema.proto.annotations:
            if annotation.id == CXX_NAMESPACE:
                return annotation.value.text.replace('::', '.').strip('.')
        return ASSERT.unreachable(
            'expect Cxx.namespace annotation: {}', schema
        )

    @staticmethod
    def _get_object_path(schema, id_to_schema):
        parts = []
        while schema and not schema.proto.is_file():
            parts.append(ASSERT.not_none(schema.short_display_name))
            schema = id_to_schema.get(schema.proto.scope_id)
        parts.reverse()
        return '.'.join(parts)


#
# C++ ``capnp::schema`` namespace types.
#


# Use this to work around cyclic reference to ``_Schema.Value``.
def _to_value(raw):
    return _Schema.Value(raw)


# Namespace class to avoid conflicts.
class _Schema:

    class Node(bases.Base):

        class Struct(bases.Base):

            _raw_type = _capnp.schema.Node.Struct

            is_group = bases.def_p(_raw_type.getIsGroup)

        _raw_type = _capnp.schema.Node

        __repr__ = classes.make_repr(
            'id={self.id} '
            'scope_id={self.scope_id} '
            'display_name={self.display_name!r} '
            'which={self.which}'
        )

        id = bases.def_p(_raw_type.getId)

        display_name = bases.def_mp(
            'display_name',
            bases.to_str,
            _raw_type.getDisplayName,
        )

        display_name_prefix_length = bases.def_p(
            _raw_type.getDisplayNamePrefixLength
        )

        scope_id = bases.def_p(_raw_type.getScopeId)

        @classes.memorizing_property
        def annotations(self):
            return tuple(map(_Schema.Annotation, self._raw.getAnnotations()))

        which = bases.def_p(_raw_type.which)

        is_file = bases.def_f0(_raw_type.isFile)
        is_struct = bases.def_f0(_raw_type.isStruct)
        is_enum = bases.def_f0(_raw_type.isEnum)
        is_interface = bases.def_f0(_raw_type.isInterface)
        is_const = bases.def_f0(_raw_type.isConst)
        is_annotation = bases.def_f0(_raw_type.isAnnotation)

        struct = bases.def_mp('struct', Struct, _raw_type.getStruct)

    class Field(bases.Base):

        class Slot(bases.Base):

            _raw_type = _capnp.schema.Field.Slot

            had_explicit_default = bases.def_p(_raw_type.getHadExplicitDefault)

        _raw_type = _capnp.schema.Field

        __repr__ = classes.make_repr(
            'name={self.name!r} code_order={self.code_order}'
        )

        name = bases.def_mp('name', bases.to_str, _raw_type.getName)

        code_order = bases.def_p(_raw_type.getCodeOrder)

        which = bases.def_p(_raw_type.which)
        is_slot = bases.def_f0(_raw_type.isSlot)
        is_group = bases.def_f0(_raw_type.isGroup)

        slot = bases.def_mp('slot', Slot, _raw_type.getSlot)

    class Enumerant(bases.Base):

        _raw_type = _capnp.schema.Enumerant

        __repr__ = classes.make_repr(
            'name={self.name!r} code_order={self.code_order}'
        )

        name = bases.def_mp('name', bases.to_str, _raw_type.getName)

        code_order = bases.def_p(_raw_type.getCodeOrder)

    class Value(bases.Base):

        _raw_type = _capnp.schema.Value

        __repr__ = classes.make_repr('which={self.which}')

        which = bases.def_p(_raw_type.which)

        is_void = bases.def_f0(_raw_type.isVoid)
        is_bool = bases.def_f0(_raw_type.isBool)
        is_int8 = bases.def_f0(_raw_type.isInt8)
        is_int16 = bases.def_f0(_raw_type.isInt16)
        is_int32 = bases.def_f0(_raw_type.isInt32)
        is_int64 = bases.def_f0(_raw_type.isInt64)
        is_uint8 = bases.def_f0(_raw_type.isUint8)
        is_uint16 = bases.def_f0(_raw_type.isUint16)
        is_uint32 = bases.def_f0(_raw_type.isUint32)
        is_uint64 = bases.def_f0(_raw_type.isUint64)
        is_float32 = bases.def_f0(_raw_type.isFloat32)
        is_float64 = bases.def_f0(_raw_type.isFloat64)
        is_text = bases.def_f0(_raw_type.isText)
        is_data = bases.def_f0(_raw_type.isData)
        is_list = bases.def_f0(_raw_type.isList)
        is_enum = bases.def_f0(_raw_type.isEnum)
        is_struct = bases.def_f0(_raw_type.isStruct)
        is_interface = bases.def_f0(_raw_type.isInterface)
        is_any_pointer = bases.def_f0(_raw_type.isAnyPointer)

        @classes.memorizing_property
        def text(self):
            ASSERT.true(self._raw.isText())
            return str(self._raw.getText(), 'utf8')

    class Annotation(bases.Base):

        _raw_type = _capnp.schema.Annotation

        __repr__ = classes.make_repr('id={self.id} value={self.value}')

        id = bases.def_p(_raw_type.getId)

        value = bases.def_mp('value', _to_value, _raw_type.getValue)


#
# C++ ``capnp`` namespace types.
#


# Use this to work around cyclic reference to ``Type``.
def _to_type(raw):
    return Type(raw)


class Schema(bases.Base):

    _raw_type = _capnp.Schema

    __repr__ = classes.make_repr('proto={self.proto!r}')

    proto = bases.def_mp('proto', _Schema.Node, _raw_type.getProto)

    is_branded = bases.def_f0(_raw_type.isBranded)

    # Use explicit functional form to work around cyclic reference in
    # the ``asX`` methods below.

    def as_struct(self):
        return StructSchema(self._raw.asStruct())

    def as_enum(self):
        return EnumSchema(self._raw.asEnum())

    def as_interface(self):
        return InterfaceSchema(self._raw.asInterface())

    def as_const(self):
        return ConstSchema(self._raw.asConst())

    short_display_name = bases.def_mp(
        'short_display_name',
        bases.to_str,
        _raw_type.getShortDisplayName,
    )


class StructSchema(Schema):

    class Field(bases.Base):

        _raw_type = _capnp.StructSchema.Field

        __repr__ = classes.make_repr(
            'proto={self.proto!r} index={self.index} type={self.type!r}'
        )

        proto = bases.def_mp('proto', _Schema.Field, _raw_type.getProto)

        index = bases.def_p(_raw_type.getIndex)

        type = bases.def_mp('type', _to_type, _raw_type.getType)

    _raw_type = _capnp.StructSchema

    __repr__ = classes.make_repr()

    @classes.memorizing_property
    def fields(self):
        return {
            f.proto.name: f
            for f in map(StructSchema.Field, self._raw.getFields())
        }

    @classes.memorizing_property
    def union_fields(self):
        return {
            f.proto.name: f
            for f in map(StructSchema.Field, self._raw.getUnionFields())
        }

    @classes.memorizing_property
    def non_union_fields(self):
        return {
            f.proto.name: f
            for f in map(StructSchema.Field, self._raw.getNonUnionFields())
        }


class EnumSchema(Schema):

    class Enumerant(bases.Base):

        _raw_type = _capnp.EnumSchema.Enumerant

        __repr__ = classes.make_repr(
            'proto={self.proto!r} ordinal={self.ordinal} index={self.index}'
        )

        proto = bases.def_mp('proto', _Schema.Enumerant, _raw_type.getProto)

        ordinal = bases.def_p(_raw_type.getOrdinal)

        index = bases.def_p(_raw_type.getIndex)

    _raw_type = _capnp.EnumSchema

    __repr__ = classes.make_repr()

    @classes.memorizing_property
    def enumerants(self):
        return {
            e.proto.name: e
            for e in map(EnumSchema.Enumerant, self._raw.getEnumerants())
        }


class InterfaceSchema(Schema):

    _raw_type = _capnp.InterfaceSchema

    __repr__ = classes.make_repr()


class ConstSchema(Schema):

    _raw_type = _capnp.ConstSchema

    __repr__ = classes.make_repr('type={self.type!r}')

    type = bases.def_mp('type', _to_type, _raw_type.getType)


class ListSchema(bases.Base):

    _raw_type = _capnp.ListSchema

    __repr__ = classes.make_repr('element_type={self.element_type!r}')

    element_type = bases.def_mp('type', _to_type, _raw_type.getElementType)


class Type(bases.Base):

    _raw_type = _capnp.Type

    __repr__ = classes.make_repr('which={self.which}')

    which = bases.def_p(_raw_type.which)

    as_struct = bases.def_f0(StructSchema, _raw_type.asStruct)
    as_enum = bases.def_f0(EnumSchema, _raw_type.asEnum)
    as_interface = bases.def_f0(InterfaceSchema, _raw_type.asInterface)
    as_list = bases.def_f0(ListSchema, _raw_type.asList)

    is_void = bases.def_f0(_raw_type.isVoid)
    is_bool = bases.def_f0(_raw_type.isBool)
    is_int8 = bases.def_f0(_raw_type.isInt8)
    is_int16 = bases.def_f0(_raw_type.isInt16)
    is_int32 = bases.def_f0(_raw_type.isInt32)
    is_int64 = bases.def_f0(_raw_type.isInt64)
    is_uint8 = bases.def_f0(_raw_type.isUInt8)
    is_uint16 = bases.def_f0(_raw_type.isUInt16)
    is_uint32 = bases.def_f0(_raw_type.isUInt32)
    is_uint64 = bases.def_f0(_raw_type.isUInt64)
    is_float32 = bases.def_f0(_raw_type.isFloat32)
    is_float64 = bases.def_f0(_raw_type.isFloat64)
    is_text = bases.def_f0(_raw_type.isText)
    is_data = bases.def_f0(_raw_type.isData)
    is_list = bases.def_f0(_raw_type.isList)
    is_enum = bases.def_f0(_raw_type.isEnum)
    is_struct = bases.def_f0(_raw_type.isStruct)
    is_interface = bases.def_f0(_raw_type.isInterface)
    is_any_pointer = bases.def_f0(_raw_type.isAnyPointer)
