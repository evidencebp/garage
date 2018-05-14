"""Meta build rules."""

from foreman import define_rule


(define_rule('all')
 .with_doc('Build all packages.')
 .depend('//host/buildtools:install')
 .depend('//py/capnp:build')
 .depend('//py/garage:build')
 .depend('//py/http2:build')
 .depend('//py/imagetools:build')
 .depend('//py/nanomsg:build')
 .depend('//py/startup:build')
 .depend('//py/v8:build')
 .depend('third-party')
)


(define_rule('third-party')
 .with_doc('Build all third-party packages and third-party host tools.')
 .depend('configure-boost')
 .depend('//cc/boost:build')
 .depend('//cc/capnproto:build')
 .depend('//cc/nanomsg:build')
 .depend('//cc/nghttp2:build')
 .depend('//cc/v8:build')
 .depend('//host/capnproto-java:install')
 .depend('//host/cpython:install')
 .depend('//host/cython:install')
 .depend('//host/depot_tools:install')
 .depend('//host/gradle:install')
 .depend('//host/java:install')
 .depend('//host/node:install')
 .depend('//java/java:build')
 .depend('//py/cpython:build')
 .depend('//py/curio:build')
 .depend('//py/lxml:build')
 .depend('//py/mako:build')
 .depend('//py/pyyaml:build')
 .depend('//py/pyyaml-zipapp:patch')
 .depend('//py/requests:build')
 .depend('//py/sqlalchemy:build')
)


#
# NOTE: This may look bending over backward, but given how the extended
# dependency graph is generated by foreman, you have to express the
# dependencies this way.  Why?  If instead you express the dependencies
# this way:
#
#     (define_rule('//meta:third-party')
#      .depend('//cc/boost:config', parameters={'//cc/boost:libraries': ['python']})
#      .depend('//cc/boost:build'))
#
#     (define_rule('//cc/boost:config')
#      .reverse_depend('//cc/boost:build'))
#
# The extended dependency graph will actually be:
#
#     //meta:third-party() --+--> //cc/boost:config(libraries=python)
#                            |
#                            +--> //cc/boost:build() -.-.-> //cc/boost:config()
#
# Where -----> denotes normal dependency and -.-.-> denotes reverse
# dependency.  The extended rule //cc/boost:build() only depends on
# non-configured //cc/boost:config(), and thus there is no guarantee
# that //cc/boost:build() is executed after //cc/boost:config(libraries=python).
#
(define_rule('configure-boost')
 .depend('//cc/boost:config', parameters={'//cc/boost:libraries': ['python']})
 .reverse_depend('//cc/boost:build')
)
