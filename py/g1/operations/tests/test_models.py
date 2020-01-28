import unittest

from g1.containers import models as ctr_models
from g1.operations import models


class ModelsTest(unittest.TestCase):

    def test_validate_absolute_label(self):
        match = models._ABSOLUTE_LABEL_PATTERN.fullmatch('//a-b/c-d/e-f:g-h')
        self.assertIsNotNone(match)
        self.assertEqual(match.group('path'), 'a-b/c-d/e-f')
        self.assertEqual(match.group('name'), 'g-h')
        for valid_label in (
            '//a/b/c:d',
            '//a-b-c-d:e-f-g-h',
        ):
            with self.subTest(valid_label):
                models.validate_absolute_label(valid_label)
        for invalid_label in (
            '//x',
            '/x',
            '/x:y',
            'x',
            'x:y',
            ':x',
            ':',
            '//a_b:x-y',
            '//a/b_c:x-y',
            '//a-b:x_y',
            '//a-b:x-y/',
            '//a-b:x-y/z',
        ):
            with self.subTest(invalid_label):
                with self.assertRaises(AssertionError):
                    models.validate_absolute_label(invalid_label)

    def test_not_unique_image_names(self):
        with self.assertRaisesRegex(
            AssertionError,
            r'expect unique image names:',
        ):
            models.PodDeployInstruction(
                pod_config_template=ctr_models.PodConfig(
                    name='dummy',
                    version='0.0.1',
                    apps=[],
                    images=[
                        ctr_models.PodConfig.Image(
                            name='dummy',
                            version='0.0.1',
                        ),
                        ctr_models.PodConfig.Image(
                            name='dummy',
                            version='0.0.2',
                        ),
                    ],
                ),
                volumes=[],
            )

    def test_not_unique_volume_names(self):
        with self.assertRaisesRegex(
            AssertionError,
            r'expect unique volume names:',
        ):
            models.PodDeployInstruction(
                pod_config_template=ctr_models.PodConfig(
                    name='dummy',
                    version='0.0.1',
                    apps=[],
                    images=[
                        ctr_models.PodConfig.Image(
                            name='dummy',
                            version='0.0.1',
                        ),
                    ],
                ),
                volumes=[
                    models.PodDeployInstruction.Volume(
                        label='//a:x',
                        version='0.0.1',
                        target='/a',
                    ),
                    models.PodDeployInstruction.Volume(
                        label='//b:x',
                        version='0.0.2',
                        target='/b',
                    ),
                ],
            )


if __name__ == '__main__':
    unittest.main()
