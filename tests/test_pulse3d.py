import ctypes
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


class FakeHidFunction:
    def __call__(self, *args):
        return 0


class FakeHidApi:
    def __getattr__(self, name):
        return FakeHidFunction()


def load_pulse3d():
    module_path = Path(__file__).parents[1] / "pulse3d.py"
    spec = importlib.util.spec_from_file_location("pulse3d", module_path)
    module = importlib.util.module_from_spec(spec)

    with patch.object(ctypes, "CDLL", return_value=FakeHidApi()):
        spec.loader.exec_module(module)

    return module


pulse3d = load_pulse3d()


class GetValueTests(unittest.TestCase):
    def test_reads_all_sensor_values(self):
        report = bytes([0xB0, 0, 35, 82, 0xED, 0, 0, 64])

        self.assertEqual(pulse3d.get_value("pulse3d_battery", report), "82")
        self.assertEqual(pulse3d.get_value("pulse3d_volume", report), "64")
        self.assertEqual(
            pulse3d.get_value("pulse3d_chat_game", report),
            "35",
        )
        self.assertEqual(pulse3d.get_value("pulse3d_mute", report), "0")

    def test_converts_muted_state(self):
        report = bytes([0xB0, 0, 0, 0, 0xEF, 0, 0, 0])

        self.assertEqual(pulse3d.get_value("pulse3d_mute", report), "1")

    def test_rejects_invalid_or_transitional_values(self):
        battery = bytes([0xB0, 0, 0, 0x80, 0xED, 0, 0, 0])
        volume = bytes([0xB0, 0, 0, 0, 0xED, 0, 0, 0xFF])
        chat_game = bytes([0xB0, 0, 0xFF, 0, 0xED, 0, 0, 0])
        mute = bytes([0xB0, 0, 0, 0, 0x00, 0, 0, 0])

        self.assertIsNone(pulse3d.get_value("pulse3d_battery", battery))
        self.assertIsNone(pulse3d.get_value("pulse3d_volume", volume))
        self.assertIsNone(pulse3d.get_value("pulse3d_chat_game", chat_game))
        self.assertIsNone(pulse3d.get_value("pulse3d_mute", mute))

    def test_rejects_missing_report_and_unknown_sensor(self):
        self.assertIsNone(pulse3d.get_value("pulse3d_battery", None))
        self.assertIsNone(pulse3d.get_value("unknown", bytes(8)))


class SensorMetadataTests(unittest.TestCase):
    def test_exposes_expected_sensors(self):
        self.assertEqual(
            pulse3d.SENSORS,
            (
                "pulse3d_battery",
                "pulse3d_volume",
                "pulse3d_chat_game",
                "pulse3d_mute",
            ),
        )

    def test_reports_percentage_ranges(self):
        for sensor in pulse3d.SENSORS[:3]:
            self.assertEqual(pulse3d.get_property(sensor, "min"), "0")
            self.assertEqual(pulse3d.get_property(sensor, "max"), "100")
            self.assertEqual(pulse3d.get_property(sensor, "unit"), "%")


if __name__ == "__main__":
    unittest.main()