import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from palworld_one_shot_update import (  # noqa: E402
    merge_settings,
    parse_fields,
    select_newest,
    version_tuple,
)


class VersionTests(unittest.TestCase):
    def test_version_tuple_accepts_supported_tags(self):
        self.assertEqual(version_tuple("v1.0.0.100"), (1, 0, 0, 100))
        self.assertEqual(version_tuple("0.7.3.90464"), (0, 7, 3, 90464))

    def test_version_tuple_ignores_non_version_tags(self):
        self.assertIsNone(version_tuple("latest"))
        self.assertIsNone(version_tuple("v1.0"))

    def test_select_newest_sorts_numerically(self):
        tags = ["latest", "v0.7.3.90464", "v1.0.0.12", "v1.0.0.9"]
        self.assertEqual(select_newest(tags), "v1.0.0.12")


class SettingsTests(unittest.TestCase):
    def test_parse_fields_keeps_nested_commas(self):
        body = 'ServerName="Test",CrossplayPlatforms=(Steam,Xbox,PS5),Max=4'
        self.assertEqual(
            parse_fields(body),
            [
                ("ServerName", '"Test"'),
                ("CrossplayPlatforms", "(Steam,Xbox,PS5)"),
                ("Max", "4"),
            ],
        )

    def test_merge_appends_new_defaults_and_preserves_existing_values(self):
        active = (
            "[/Script/Pal.PalGameWorldSettings]\n"
            'OptionSettings=(ServerName="moha-eos",Max=4,CrossplayPlatforms=(Steam,Xbox))\n'
        )
        defaults = (
            "[/Script/Pal.PalGameWorldSettings]\n"
            'OptionSettings=(ServerName="Default",Max=32,NewOne=True,NewList=(A,B))\n'
        )

        merged, added = merge_settings(active, defaults)

        self.assertIn('ServerName="moha-eos"', merged)
        self.assertIn("Max=4", merged)
        self.assertIn("CrossplayPlatforms=(Steam,Xbox)", merged)
        self.assertIn("NewOne=True", merged)
        self.assertIn("NewList=(A,B)", merged)
        self.assertEqual(added, ["NewOne", "NewList"])

    def test_merge_is_unchanged_when_no_keys_are_missing(self):
        active = "[x]\nOptionSettings=(A=9,B=False)\n"
        defaults = "[x]\nOptionSettings=(A=1,B=True)\n"
        self.assertEqual(merge_settings(active, defaults), (active, []))


if __name__ == "__main__":
    unittest.main()
