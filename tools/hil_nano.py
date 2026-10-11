#!/usr/bin/env python3
"""Hardware smoke test for the Arduino Nano ESP32: flash the build, reset the board and check it.

It checks that the board runs the firmware just built, finds its 8 MB of octal PSRAM, runs from the
first OTA slot of its 16 MB flash, and answers on the setup protocol and the developer console.
Run it after `tools/firmware.sh build nano_esp32`, with the board on USB:

  tools/hil_nano.py              flash, reset and check
  tools/hil_nano.py --fresh      also erase the saved settings, so the board starts as a new owl
  tools/hil_nano.py --rom        the board waits in ROM download mode (first flash or recovery,
                                 see docs/dev-board-nano-esp32.md)
  tools/hil_nano.py --no-flash   only reset and check
  tools/hil_nano.py --wifi       also join Wi-Fi: OWL_WIFI_SSID and OWL_WIFI_PASSWORD come from the
                                 environment or from private/hil.env (never from the command line)
  tools/hil_nano.py --missing-network
                                 also save only a network that is never in range (no credentials
                                 needed): the owl reports it, backs off, and goes idle once it is
                                 removed again

Opening the serial port resets this board (the USB-Serial/JTAG controller restarts the chip, reset
reason "usb"), so the script waits for the boot line after every open.

Console logs go to build/hil-nano/console.log.
"""

from __future__ import annotations

import argparse
import calendar
import ipaddress
import json
import os
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from owl_serial import Board, BoardError, find_port, load_env_file  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILD = ROOT / "build" / "firmware-nano_esp32"
WORK = ROOT / "build" / "hil-nano"
NVS_OFFSET, NVS_SIZE = 0x9000, 0x14000  # firmware/partitions.csv
HEAP_FLOOR_KB = 32  # internal RAM that must stay free at the lowest point since boot
MISSING_SSID = "owltunes-hil-missing"  # a network that is never in range
DUMMY_PASSWORD = "dummy-pw-5f3a9c71"  # for that network; unlike its SSID it appears nowhere else
# The ranges the setup page accepts as a LAN address (P2): 10/8, 172.16/12, 192.168/16, 169.254/16.
LAN_NETWORKS = tuple(ipaddress.IPv4Network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
                                                         "169.254.0.0/16"))


class Failure(Exception):
    pass


def check(condition: bool, what: str) -> None:
    if not condition:
        raise Failure(what)
    print(f"ok - {what}", flush=True)


def esptool(args: list[str], cwd: pathlib.Path = ROOT, may_fail: bool = False, timeout: float = 120.0) -> bool:
    try:
        result = subprocess.run([sys.executable, "-m", "esptool", "--chip", "esp32s3", *args], cwd=cwd,
                                timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Failure(f"esptool {' '.join(args)} did not finish within {timeout:.0f} s") from None
    if result.returncode != 0 and not may_fail:
        raise Failure(f"esptool {' '.join(args)} failed")
    return result.returncode == 0


def built_version() -> str:
    description = BUILD / "project_description.json"
    if not description.exists():
        raise Failure("no build: run tools/firmware.sh build nano_esp32 first")
    return json.loads(description.read_text())["project_version"]


def flash(port: str, rom: bool, fresh: bool) -> None:
    """Write the build. From ROM download mode only a watchdog reset starts the app afterwards."""
    before, after = ("no-reset", "watchdog-reset") if rom else ("default-reset", "hard-reset")
    args = ["--port", port, "--baud", "460800", "--before", before, "--after", after, "write-flash", "@flash_args"]
    if fresh:
        blank = WORK / "blank_nvs.bin"
        blank.write_bytes(b"\xff" * NVS_SIZE)
        args += [hex(NVS_OFFSET), str(blank)]
    esptool(args, cwd=BUILD, timeout=120.0)


def connect(port: str, log: pathlib.Path) -> tuple[Board, dict]:
    """Open the console and get a hello. A board left in download mode gets a watchdog reset."""
    time.sleep(1.5)  # after esptool's reset the board leaves USB and comes back as a new device
    board = Board(port, log)  # opening the port resets this board (reset reason "usb")
    try:
        try:
            board.wait_boot(timeout=20)
            return board, board.hello(timeout=25)
        except BoardError:
            print("no answer: trying a watchdog reset in case the board is still in download mode", flush=True)
            board.close()
            esptool(["--port", port, "--before", "no-reset", "--after", "watchdog-reset", "chip-id"],
                    may_fail=True, timeout=30.0)
            board.open()
            board.wait_boot(timeout=20, since=board.mark())
            return board, board.hello(timeout=25)
    except BaseException:
        board.close()
        raise


def boot_checks(board: Board, hello: dict, fresh: bool) -> dict:
    check(hello.get("fw") == built_version(), f"the board runs the firmware just built ({hello.get('fw')})")
    check(hello.get("protocol") == 1 and str(hello.get("name", "")).startswith("OwlTunes-"),
          f"the setup protocol answers ({hello.get('name')})")
    info = board.command("info", "info")
    check(info.get("board") == "nano_esp32", "the console reports the Nano ESP32 board")
    check(info.get("uptime_s", 999) < 60, f"it started just now (reset reason {info.get('reset')})")
    check(info.get("psram_kb") == 8192 and info.get("psram_free_kb", 0) > 4096,
          f"8 MB of octal PSRAM is found ({info.get('psram_free_kb')} KB free)")
    check(info.get("flash_kb") == 16384 and info.get("partition") == "ota_0",
          "the app runs from the first OTA slot of the 16 MB flash")
    check(info.get("heap_min_kb", 0) >= HEAP_FLOOR_KB,
          f"internal RAM stayed above {HEAP_FLOOR_KB} KB ({info.get('heap_min_kb')} KB at its lowest)")
    if fresh:
        check(info.get("status") == "needs_wifi" and info.get("led") == "#000040",
              "a new owl asks for Wi-Fi with a slowly blinking blue LED")
    refused = board.command("frobnicate", "cmd", "refused")
    check(refused.get("error") == "unknown_cmd", "the console refuses an unknown command")
    return info


def wifi_credentials() -> tuple[str, str]:
    env = {**load_env_file(ROOT / "private" / "hil.env"), **os.environ}
    ssid, password = env.get("OWL_WIFI_SSID", ""), env.get("OWL_WIFI_PASSWORD", "")
    if not ssid:
        raise Failure("--wifi needs OWL_WIFI_SSID and OWL_WIFI_PASSWORD (environment or private/hil.env)")
    return ssid, password


def private_ipv4(text: str) -> bool:
    try:
        address = ipaddress.IPv4Address(text)
    except ValueError:
        return False
    return any(address in network for network in LAN_NETWORKS)


def password_not_logged(log: pathlib.Path, password: str) -> None:
    """The console log holds everything the board printed; a Wi-Fi password must never be in it."""
    if password:
        check(password not in log.read_text(encoding="utf-8", errors="replace"),
              "the console log never shows the Wi-Fi password sent in this run")


def utc_seconds(text: str) -> float:
    """Seconds since 1970 for "2026-10-11T09:30:00Z"; 0 when the text is not such a time."""
    try:
        return float(calendar.timegm(time.strptime(text, "%Y-%m-%dT%H:%M:%SZ")))
    except ValueError:
        return 0.0


def wifi_checks(board: Board) -> None:
    """Join the test network, with a network that is not in range saved ahead of it, then rejoin
    after a reset. The password is sent to the board only; it is never printed or logged."""
    ssid, password = wifi_credentials()
    saved = board.hello().get("networks", [])
    others = [name for name in saved if name not in (ssid, MISSING_SSID)]
    for name in (MISSING_SSID, ssid):
        if name in saved:
            board.request("wifi_remove", ssid=name)
    since = board.mark()  # events from before the removals are stale
    if others:
        print(f"note - not checking the not-found report: other networks are saved ({', '.join(others)})")
    else:
        check(board.request("wifi_add", ssid=MISSING_SSID, password=DUMMY_PASSWORD).get("ok") is True,
              "a network that is never in range is saved first")
    check(board.request("wifi_add", ssid=ssid, password=password).get("ok") is True, f"{ssid} is saved next")
    up_since = board.mark()  # after the removals took effect: an "up" from before them is stale
    if not others:
        failed = board.wait_event("network", "failed", timeout=60, since=since,
                                  where=lambda m: m.get("ssid") == MISSING_SSID)
        up_since = board.mark()  # the missing network is tried first, so the join follows this event
        check(failed.get("error") == "wifi_not_found", "the owl reports the network it cannot find")
    up = board.wait_event("network", "up", timeout=90, since=up_since)
    check(private_ipv4(up.get("ip", "")), f"then it joins {ssid} and gets an address ({up.get('ip')})")
    synced = board.wait_event("time", "synced", timeout=60, since=since)
    check(abs(utc_seconds(synced.get("utc", "")) - time.time()) < 120, f"the clock is set from NTP ({synced.get('utc')})")
    if not others:
        check(board.request("wifi_remove", ssid=MISSING_SSID).get("ok") is True, "the missing network is removed")
    info = board.command("info", "info")
    check(info.get("wifi") == "online" and info.get("ssid") == ssid and -100 < info.get("rssi", 0) < 0,
          f"info shows the joined network (signal {info.get('rssi')} dBm, status {info.get('status')})")
    board.wait_boot(since=board.reset(), timeout=20)
    board.hello()
    deadline = time.monotonic() + 60
    while (info := board.command("info", "info")).get("ip", "") == "":
        if time.monotonic() > deadline:
            raise Failure("after a reset the owl did not rejoin its network within 60 s")
        time.sleep(2)
    check(info.get("ssid") == ssid, "after a reset the owl rejoins the saved network by itself")
    check(info.get("heap_min_kb", 0) >= HEAP_FLOOR_KB,
          f"internal RAM stayed above {HEAP_FLOOR_KB} KB while joining ({info.get('heap_min_kb')} KB at its lowest)")


def missing_network_checks(board: Board) -> None:
    """Save only a network that is never in range. The owl must report that it cannot find it, wait
    5 s before the next round and 10 s before the one after, and go idle once it is removed. Needs
    no Wi-Fi credentials and leaves no network saved."""
    saved = board.hello().get("networks", [])
    others = [name for name in saved if name != MISSING_SSID]
    if others:
        raise Failure(f"other networks are saved ({', '.join(others)}): remove them, or flash with --fresh")
    if MISSING_SSID in saved:
        board.request("wifi_remove", ssid=MISSING_SSID)
    since = board.mark()
    check(board.request("wifi_add", ssid=MISSING_SSID, password=DUMMY_PASSWORD).get("ok") is True,
          "a network that is never in range is saved")
    seen: list[float] = []
    for attempt in range(3):
        failed = board.wait_event("network", "failed", timeout=60, since=since,
                                  where=lambda m: m.get("ssid") == MISSING_SSID)
        seen.append(time.monotonic())
        since = board.mark()
        if attempt == 0:
            check(failed.get("error") == "wifi_not_found", "the owl reports the network it cannot find")
            info = board.command("info", "info")
            check(info.get("wifi") == "waiting" and info.get("ssid") == "" and info.get("status") == "joining",
                  f"then it waits before trying again (wifi {info.get('wifi')}, status {info.get('status')})")
    first, second = seen[1] - seen[0], seen[2] - seen[1]
    check(first >= 4.5 and second >= 9.5 and second > first + 3,
          f"it waits longer after each failed round ({first:.1f} s, then {second:.1f} s)")
    check(board.request("wifi_remove", ssid=MISSING_SSID).get("ok") is True, "the missing network is removed")
    deadline = time.monotonic() + 10
    while (info := board.command("info", "info")).get("wifi") != "idle":
        if time.monotonic() > deadline:
            raise Failure(f"with no network saved the owl stays {info.get('wifi')}")
        time.sleep(1)
    check(info.get("status") == "needs_wifi", "with no network saved the owl stops and asks for Wi-Fi")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", help="serial port (default: the one /dev/serial/by-id/*Espressif* device)")
    parser.add_argument("--no-flash", action="store_true", help="only reset the board and check it")
    parser.add_argument("--rom", action="store_true", help="the board waits in ROM download mode")
    parser.add_argument("--fresh", action="store_true", help="erase the saved settings while flashing")
    parser.add_argument("--wifi", action="store_true", help="also join Wi-Fi (see above)")
    parser.add_argument("--missing-network", action="store_true",
                        help="also check the report and backoff for a network that is never in range")
    args = parser.parse_args()
    try:
        import serial  # noqa: F401  (pyserial; the ESP-IDF Python has it)
        import esptool  # noqa: F401
    except ImportError:
        idf_python = pathlib.Path(os.environ.get("IDF_PYTHON_ENV_PATH", "/nonexistent"), "bin", "python")
        if idf_python.exists() and pathlib.Path(sys.executable) != idf_python:
            os.execv(idf_python, [str(idf_python), __file__, *sys.argv[1:]])
        print("cannot find pyserial and esptool (activate ESP-IDF v6.1 first)", file=sys.stderr)
        return 2
    WORK.mkdir(parents=True, exist_ok=True)
    log = WORK / "console.log"
    log.write_text("")
    board = None
    try:
        port = find_port(args.port)
        if args.no_flash:
            board, _ = connect(port, log)
            since = board.reset()
            board.wait_boot(since=since, timeout=20)
            hello = board.hello()
        else:
            flash(port, args.rom, args.fresh)
            board, hello = connect(port, log)
        boot_checks(board, hello, args.fresh)
        passwords = []
        if args.missing_network:
            missing_network_checks(board)
            passwords.append(DUMMY_PASSWORD)
        if args.wifi:
            wifi_checks(board)
            passwords += [DUMMY_PASSWORD, wifi_credentials()[1]]
        for password in passwords:
            password_not_logged(log, password)
    except (Failure, BoardError) as err:
        print(f"FAIL - {err} (console log in {log})", file=sys.stderr)
        return 1
    finally:
        if board is not None:
            board.close()
    print("Nano ESP32 hardware test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
