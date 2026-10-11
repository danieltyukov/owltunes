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


class WifiCredentialsTest(unittest.TestCase):
    def credentials(self, env_file, environ):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(hil_nano, "ROOT", pathlib.Path(d)), \
                mock.patch.dict(hil_nano.os.environ, environ, clear=True):
            if env_file is not None:
                pathlib.Path(d, "private").mkdir()
                pathlib.Path(d, "private", "hil.env").write_text(env_file)
            return hil_nano.wifi_credentials()

    def test_read_from_the_private_file(self):
        self.assertEqual(self.credentials("OWL_WIFI_SSID=Home\nOWL_WIFI_PASSWORD=secret12\n", {}),
                         ("Home", "secret12"))

    def test_the_environment_wins(self):
        self.assertEqual(self.credentials("OWL_WIFI_SSID=Home\n", {"OWL_WIFI_SSID": "Lab"}), ("Lab", ""))

    def test_no_network_is_a_failure(self):
        with self.assertRaises(hil_nano.Failure):
            self.credentials(None, {})


class PrivateIpv4Test(unittest.TestCase):
    def test_lan_addresses(self):
        for ip in ("192.168.1.23", "10.0.0.5", "172.16.4.1"):
            self.assertTrue(hil_nano.private_ipv4(ip), ip)

    def test_public_empty_or_garbage(self):
        for ip in ("8.8.8.8", "", "192.168.1", "fe80::1"):
            self.assertFalse(hil_nano.private_ipv4(ip), ip)


class MissingNetworkBoard:
    """Answers like a board with only the missing network saved, failing it every round."""

    def __init__(self, saved=(), error="wifi_not_found", wifi_after_failure="waiting"):
        self.saved = list(saved)
        self.error = error
        self.wifi_after_failure = wifi_after_failure
        self.requests = []

    def hello(self):
        return {"networks": list(self.saved)}

    def mark(self):
        return 0

    def request(self, cmd, **params):
        self.requests.append((cmd, params.get("ssid")))
        if cmd == "wifi_add":
            self.saved.append(params["ssid"])
        elif cmd == "wifi_remove":
            self.saved.remove(params["ssid"])
        return {"ok": True}

    def wait_event(self, event, state=None, timeout=30, since=0, where=None):
        msg = {"event": event, "state": state, "ssid": hil_nano.MISSING_SSID, "error": self.error}
        assert where is None or where(msg)
        return msg

    def command(self, text, event, state=None, timeout=10, where=None):
        if self.saved:
            return {"wifi": self.wifi_after_failure, "ssid": "", "status": "joining"}
        return {"wifi": "idle", "ssid": "", "status": "needs_wifi"}


class MissingNetworkChecksTest(unittest.TestCase):
    def run_checks(self, board, failures_at=(100.0, 107.4, 119.8)):
        clock = iter([*failures_at, *range(200, 260)])
        with mock.patch.object(hil_nano.time, "monotonic", side_effect=lambda: float(next(clock))), \
                mock.patch.object(hil_nano.time, "sleep"), mock.patch("builtins.print"):
            hil_nano.missing_network_checks(board)

    def test_report_backoff_and_cleanup_pass(self):
        board = MissingNetworkBoard()
        self.run_checks(board)
        self.assertEqual(board.requests, [("wifi_add", hil_nano.MISSING_SSID),
                                          ("wifi_remove", hil_nano.MISSING_SSID)])
        self.assertEqual(board.saved, [])

    def test_other_saved_networks_stop_the_check(self):
        board = MissingNetworkBoard(saved=["Home"])
        with self.assertRaises(hil_nano.Failure):
            self.run_checks(board)
        self.assertEqual(board.requests, [])

    def test_a_wrong_error_code_fails(self):
        with self.assertRaises(hil_nano.Failure):
            self.run_checks(MissingNetworkBoard(error="wifi_failed"))

    def test_no_wait_between_rounds_fails(self):
        with self.assertRaises(hil_nano.Failure):
            self.run_checks(MissingNetworkBoard(), failures_at=(100.0, 102.4, 104.8))

    def test_a_wait_that_does_not_grow_fails(self):
        with self.assertRaises(hil_nano.Failure):
            self.run_checks(MissingNetworkBoard(), failures_at=(100.0, 107.4, 114.8))

    def test_not_waiting_after_a_failure_fails(self):
        with self.assertRaises(hil_nano.Failure):
            self.run_checks(MissingNetworkBoard(wifi_after_failure="joining"))


if __name__ == "__main__":
    unittest.main()
