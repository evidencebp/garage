__all__ = [
    'PodDeployInstruction',
    'PodMetadata',
    'XarDeployInstruction',
    'XarMetadata',
]

import dataclasses
import re
import typing
from pathlib import Path

from g1.bases.assertions import ASSERT
from g1.containers import models as ctr_models

# Operations repository structure.
REPO_PODS_DIR_NAME = 'pods'
REPO_XARS_DIR_NAME = 'xars'

# Operations directory structure.
OPS_DIR_METADATA_FILENAME = 'metadata'
OPS_DIR_REFS_DIR_NAME = 'refs'
OPS_DIR_VOLUMES_DIR_NAME = 'volumes'

# Reserve this prefix for ourselves.
ENV_PREFIX = 'pod'

# Bundle directory structure.
BUNDLE_DEPLOY_INSTRUCTION_FILENAME = 'deploy.json'
POD_BUNDLE_IMAGES_DIR_NAME = 'images'
POD_BUNDLE_IMAGE_FILENAME = 'image.tar.gz'
POD_BUNDLE_VOLUMES_DIR_NAME = 'volumes'
POD_BUNDLE_VOLUME_FILENAME = 'volume.tar.gz'
XAR_BUNDLE_IMAGE_FILENAME = 'image.tar.gz'
XAR_BUNDLE_ZIPAPP_FILENAME = 'app.zip'

# For now, let's only allow a restrictive set of labels.
_ABSOLUTE_LABEL_PATTERN = re.compile(
    r'''
    //
    (?P<path>
        [a-z0-9]+(?:-[a-z0-9]+)*
        (?:/[a-z0-9]+(?:-[a-z0-9]+)*)*
    )
    :
    (?P<name>[a-z0-9]+(?:-[a-z0-9]+)*)
    ''',
    re.VERBOSE,
)


def validate_absolute_label(label):
    return ASSERT.predicate(label, _ABSOLUTE_LABEL_PATTERN.fullmatch)


def _get_label_name(pattern, label):
    return pattern.fullmatch(label).group('name')


# For now these are just an alias of the generic version validator.
_POD_LABEL_PATTERN = _ABSOLUTE_LABEL_PATTERN
validate_pod_label = validate_absolute_label
_VOLUME_LABEL_PATTERN = _ABSOLUTE_LABEL_PATTERN
validate_volume_label = validate_absolute_label
validate_volume_version = ctr_models.validate_version
validate_xar_version = ctr_models.validate_version

_XAR_LABEL_PATTERN = re.compile(
    r'''
    //
    (?P<path>
        [a-z0-9]+(?:-[a-z0-9]+)*
        (?:/[a-z0-9]+(?:-[a-z0-9]+)*)*
    )
    :
    # Allow xar names like "foo_bar.sh".
    (?P<name>[\w\-.]+)
    ''',
    re.VERBOSE,
)


def validate_xar_label(label):
    return ASSERT.predicate(label, _XAR_LABEL_PATTERN.fullmatch)


# We do not use systemd unit templates (we implement our own feature),
# and we only support service and timer unit for now.
_SYSTEMD_UNIT_NAME_PATTERN = re.compile(
    r'[a-z0-9]+(?:-[a-z0-9]+)*\.(?:service|timer)'
)


def _validate_systemd_unit_name(name):
    return ASSERT.predicate(name, _SYSTEMD_UNIT_NAME_PATTERN.fullmatch)


@dataclasses.dataclass(frozen=True)
class PodDeployInstruction:

    @dataclasses.dataclass(frozen=True)
    class Volume:
        label: str
        version: str
        target: str
        read_only: bool = True

        def __post_init__(self):
            validate_volume_label(self.label)
            validate_volume_version(self.version)
            ASSERT.predicate(Path(self.target), Path.is_absolute)

        @property
        def name(self):
            return _get_label_name(_VOLUME_LABEL_PATTERN, self.label)

    @dataclasses.dataclass(frozen=True)
    class SystemdUnit:
        name: str
        contents: str
        envs: typing.Mapping[str, str] = \
            dataclasses.field(default_factory=dict)
        auto_start: bool = True

        def __post_init__(self):
            _validate_systemd_unit_name(self.name)
            ASSERT.not_any(key.startswith(ENV_PREFIX) for key in self.envs)

    label: str
    pod_config_template: ctr_models.PodConfig
    volumes: typing.List[Volume] = ()
    systemd_units: typing.List[SystemdUnit] = ()

    def __post_init__(self):
        validate_pod_label(self.label)
        ASSERT.equal(
            _get_label_name(_POD_LABEL_PATTERN, self.label),
            self.pod_config_template.name,
        )
        # Only allow specifying image for pods by name for now.
        ASSERT.all(self.images, lambda image: image.name and image.version)
        # Due to bundle directory layout, image names and volume names
        # are expected to be unique.  (This layout restriction should be
        # not too restrictive in practice.)
        ASSERT.unique(self.images, lambda image: image.name)
        ASSERT.unique(self.volumes, lambda volume: volume.name)
        # The current implementation does not resolve any unit name
        # conflicts.
        ASSERT.unique(self.systemd_units, lambda unit: unit.name)

    # For now, version is just an alias of pod_config_template.version.
    @property
    def version(self):
        return self.pod_config_template.version

    # For now, images is just an alias of pod_config_template.images.
    @property
    def images(self):
        return self.pod_config_template.images


_SYSTEMD_UNITS_DIR_PATH = Path('/etc/systemd/system')


@dataclasses.dataclass(frozen=True)
class PodMetadata:

    @dataclasses.dataclass(frozen=True)
    class SystemdUnitConfig:
        pod_id: str
        name: str
        auto_start: bool = True

        def __post_init__(self):
            ctr_models.validate_pod_id(self.pod_id)
            _validate_systemd_unit_name(self.name)

        @property
        def unit_name(self):
            # This naming scheme should be sufficiently human-readable
            # and unlikely to conflict.
            return '%s_%s' % (
                ctr_models.generate_machine_name(self.pod_id),
                self.name,
            )

        @property
        def unit_path(self):
            return _SYSTEMD_UNITS_DIR_PATH / self.unit_name

        @property
        def unit_config_path(self):
            unit_path = self.unit_path
            return unit_path.with_name(unit_path.name + '.d') / '10-pod.conf'

    label: str
    version: str
    images: typing.List[ctr_models.PodConfig.Image]
    systemd_unit_configs: typing.List[SystemdUnitConfig] = ()

    def __post_init__(self):
        validate_pod_label(self.label)
        ctr_models.validate_pod_version(self.version)
        # Only allow specifying image for pods by name for now.
        ASSERT.all(self.images, lambda image: image.name and image.version)
        # The current implementation does not resolve any unit name
        # conflicts.
        ASSERT.unique(self.systemd_unit_configs, lambda config: config.name)


@dataclasses.dataclass(frozen=True)
class XarDeployInstruction:
    label: str
    version: str
    exec_relpath: typing.Optional[str]
    image: typing.Optional[ctr_models.PodConfig.Image]

    def __post_init__(self):
        validate_xar_label(self.label)
        validate_xar_version(self.version)
        ASSERT.not_xor(self.exec_relpath is None, self.image is None)
        if self.exec_relpath is not None:
            ASSERT.not_predicate(Path(self.exec_relpath), Path.is_absolute)

    @property
    def name(self):
        return _get_label_name(_XAR_LABEL_PATTERN, self.label)

    def is_zipapp(self):
        return self.exec_relpath is None


@dataclasses.dataclass(frozen=True)
class XarMetadata:
    label: str
    version: str
    image: typing.Optional[ctr_models.PodConfig.Image]

    def __post_init__(self):
        validate_xar_label(self.label)
        validate_xar_version(self.version)

    @property
    def name(self):
        return _get_label_name(_XAR_LABEL_PATTERN, self.label)

    def is_zipapp(self):
        return self.image is None
