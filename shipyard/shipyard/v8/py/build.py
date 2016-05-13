"""Build V8 Python binding."""

import os

import shipyard
from foreman import define_rule


def build(parameters):

    shipyard.python_pip_install(parameters, 'cython')

    build_src = shipyard.python_copy_source(
        parameters, 'v8', build_src='v8.py')

    v8_build_src = parameters['//shipyard/v8:build_src']
    if not v8_build_src.is_dir():
        raise FileExistsError('not a directory: %s' % v8_build_src)
    os.environ['V8'] = str(v8_build_src)

    v8_out = parameters['//shipyard/v8:out_target']
    if not v8_out.is_dir():
        raise FileExistsError('not a directory: %s' % v8_out)
    os.environ['V8_OUT'] = str(v8_out)

    # Remove v8/data/*.bin so that setup.py would create link to the
    # latest blobs.
    for filename in ('natives_blob.bin', 'snapshot_blob.bin'):
        blob_path = build_src / 'v8/data' / filename
        # NOTE: Path.exists() returns False on failed symlink.
        if blob_path.exists() or blob_path.is_symlink():
            blob_path.unlink()

    shipyard.python_build_package(parameters, 'v8', build_src)


(define_rule('build')
 .with_doc(__doc__)
 .with_build(build)
 .depend('//shipyard/cpython:build')
 .depend('//shipyard/v8:build')
)


(define_rule('tapeout')
 .with_doc("""Copy build artifacts.""")
 .with_build(lambda ps: shipyard.python_copy_package(ps, 'v8'))
 .depend('build')
 .depend('//shipyard/v8:tapeout')
 .reverse_depend('//shipyard/cpython:final_tapeout')
)