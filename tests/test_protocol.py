import unittest
from rgd_visual.protocol import color_packet, brightness_packet, parse_color
from rgd_visual.config import load
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ProtocolTests(unittest.TestCase):
    def test_red_matches_physically_verified_packet(self):
        self.assertEqual(color_packet("#FF0000"), bytes.fromhex("BC 04 06 00 00 03 E8 00 00 55"))

    def test_white_hue_and_saturation_zero(self):
        self.assertEqual(color_packet("#FFFFFF"), bytes.fromhex("BC 04 06 00 00 00 00 00 00 55"))

    def test_brightness_35_percent(self):
        self.assertEqual(brightness_packet(35), bytes.fromhex("BC 05 06 01 5E 00 00 00 00 55"))

    def test_invalid_brightness(self):
        for value in (-1, 101, 0.5, "30", True):
            with self.assertRaises(ValueError):
                brightness_packet(value)

    def test_invalid_color(self):
        for value in ("red", "#fff", "#gggggg", "000000"):
            with self.assertRaises(ValueError):
                parse_color(value)

    def test_user_config(self):
        settings = load(ROOT / "config.example.json")
        self.assertEqual(settings.device_address, "00:00:00:00:00:00")
        self.assertEqual(settings.states["listening"].color, "#0050FF")

if __name__ == "__main__":
    unittest.main()
