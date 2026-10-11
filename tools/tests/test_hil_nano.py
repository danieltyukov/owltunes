import csv
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import hil_nano  # noqa: E402
from owl_serial import BoardError  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

GOOD_INFO = {"board": "nano_esp32", "uptime_s": 3, "reset": "usb", "partition": "ota_0", "flash_kb": 16384,
             "psram_kb": 8192, "psram_free_kb": 8100, "heap_min_kb": 249, "status": "needs_wifi",
             "led": "#000040"}
GOOD_HELLO = {"fw": "v1.2.3", "protocol": 1, "name": "OwlTunes-7DF8"}


class FakeBoard:
    def __init__(self, info):
        self.info = info

    def command(self, text, event, state=None, timeout=10, where=None):
        if text == "info":
            return self.info
        if text == "frobnicate":
            return {"event": "cmd", "state": "refused", "error": "unknown_cmd"}
        raise BoardError(text)


class FlashTest(unittest.TestCase):
    def run_flash(self, rom, fresh):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(hil_nano, "esptool") as tool, \
                mock.patch.object(hil_nano, "WORK", pathlib.Path(d)):
            hil_nano.flash("/dev/ttyACM0", rom, fresh)
            blank = pathlib.Path(d, "blank_nvs.bin")
            size = blank.stat().st_size if blank.exists() else None
        return tool.call_args.args[0], size

    def test_normal_flash_uses_the_default_reset(self):
        args, size = self.run_flash(False, False)
        self.assertEqual(args[args.index("--before") + 1], "default-reset")
        self.assertEqual(args[args.index("--after") + 1], "hard-reset")
        self.assertIsNone(size)
        self.assertEqual(args[-2:], ["write-flash", "@flash_args"])

    def test_rom_flash_needs_a_watchdog_reset(self):
        args, _ = self.run_flash(True, False)
        self.assertEqual(args[args.index("--before") + 1], "no-reset")
        self.assertEqual(args[args.index("--after") + 1], "watchdog-reset")

    def test_only_fresh_writes_the_blank_settings_image(self):
        args, size = self.run_flash(False, True)
        self.assertEqual(args[-3], "@flash_args")
        self.assertEqual(args[-2], hex(hil_nano.NVS_OFFSET))
        self.assertEqual(size, hil_nano.NVS_SIZE)

    def test_nvs_constants_match_the_partition_table(self):
        rows = [r for r in csv.reader(line for line in (ROOT / "firmware/partitions.csv").read_text().splitlines()
                                      if line.strip() and not line.startswith("#"))]
        nvs = [[c.strip() for c in r] for r in rows if r[0].strip() == "nvs"]
        self.assertEqual(len(nvs), 1)
        self.assertEqual(int(nvs[0][3], 0), hil_nano.NVS_OFFSET)
        self.assertEqual(int(nvs[0][4], 0), hil_nano.NVS_SIZE)

    def test_a_hung_esptool_is_a_failure(self):
        import subprocess
        with mock.patch.object(hil_nano.subprocess, "run", side_effect=subprocess.TimeoutExpired("x", 1)):
            with self.assertRaises(hil_nano.Failure):
                hil_nano.esptool(["chip-id"], timeout=1)


class BuiltVersionTest(unittest.TestCase):
    def test_missing_build_is_a_failure(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(hil_nano, "BUILD", pathlib.Path(d)):
            with self.assertRaises(hil_nano.Failure):
                hil_nano.built_version()

    def test_version_is_read_from_the_build(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(hil_nano, "BUILD", pathlib.Path(d)):
            pathlib.Path(d, "project_description.json").write_text(json.dumps({"project_version": "v1.2.3"}))
            self.assertEqual(hil_nano.built_version(), "v1.2.3")


class BootChecksTest(unittest.TestCase):
    def run_checks(self, hello=None, fresh=False, **changes):
        info = {**GOOD_INFO, **changes}
        with mock.patch.object(hil_nano, "built_version", return_value="v1.2.3"), \
                mock.patch("builtins.print"):
            return hil_nano.boot_checks(FakeBoard(info), hello or GOOD_HELLO, fresh)

    def test_a_good_board_passes(self):
        self.assertEqual(self.run_checks()["board"], "nano_esp32")
        self.run_checks(fresh=True)

    def test_each_check_can_fail(self):
        for changes in ({"partition": "ota_1"}, {"heap_min_kb": 10}, {"psram_kb": 0}, {"psram_free_kb": 100},
                        {"flash_kb": 8192}, {"board": "qemu"}, {"uptime_s": 500}):
            with self.subTest(changes=changes), self.assertRaises(hil_nano.Failure):
                self.run_checks(**changes)

    def test_wrong_firmware_or_protocol_fails(self):
        for hello in ({**GOOD_HELLO, "fw": "v0.0.1"}, {**GOOD_HELLO, "protocol": 2}, {**GOOD_HELLO, "name": "x"}):
            with self.subTest(hello=hello), self.assertRaises(hil_nano.Failure):
                self.run_checks(hello=hello)

    def test_fresh_needs_the_new_owl_status(self):
        with self.assertRaises(hil_nano.Failure):
            self.run_checks(fresh=True, status="playing")


if __name__ == "__main__":
    unittest.main()
