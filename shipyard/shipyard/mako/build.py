"""Install Mako."""

import shipyard
from foreman import define_rule


(define_rule('build')
 .with_doc(__doc__)
 .with_build(lambda ps: shipyard.python_pip_install(ps, 'Mako'))
 .depend('//shipyard/cpython:build')
)


(define_rule('tapeout')
 .with_doc("""Copy build artifacts.""")
 .with_build(lambda ps: shipyard.python_copy_package(ps, 'Mako', patterns=[
     '*mako*',
     # Mako's dependency.
     'MarkupSafe',
     '*markupsafe*',
 ]))
 .depend('build')
 .reverse_depend('//shipyard/cpython:final_tapeout')
)
