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

Opening the serial port resets this board (the USB-Serial/JTAG controller restarts the chip, reset
reason "usb"), so the script waits for the boot line after every open.

Console logs go to build/hil-nano/console.log.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from owl_serial import Board, BoardError, find_port  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILD = ROOT / "build" / "firmware-nano_esp32"
WORK = ROOT / "build" / "hil-nano"
NVS_OFFSET, NVS_SIZE = 0x9000, 0x14000  # firmware/partitions.csv
HEAP_FLOOR_KB = 32  # internal RAM that must stay free at the lowest point since boot


class Failure(Exception):
    pass


def check(condition: bool, what: str) -> None:
    if not condition:
        raise Failure(what)
    print(f"ok - {what}", flush=True)


def esptool(args: list[str], cwd: pathlib.Path = ROOT, may_fail: bool = False) -> bool:
    result = subprocess.run([sys.executable, "-m", "esptool", "--chip", "esp32s3", *args], cwd=cwd)
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
    esptool(args, cwd=BUILD)


def connect(port: str, log: pathlib.Path) -> tuple[Board, dict]:
    """Open the console and get a hello. A board left in download mode gets a watchdog reset."""
    time.sleep(1.5)  # after esptool's reset the board leaves USB and comes back as a new device
    board = Board(port, log)  # opening the port resets this board (reset reason "usb")
    try:
        board.wait_boot(timeout=20)
        return board, board.hello(timeout=25)
    except BoardError:
        print("no answer: trying a watchdog reset in case the board is still in download mode", flush=True)
        board.close()
        esptool(["--port", port, "--before", "no-reset", "--after", "watchdog-reset", "chip-id"], may_fail=True)
        board.open()
        board.wait_boot(timeout=20)
        return board, board.hello(timeout=25)


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", help="serial port (default: the one /dev/serial/by-id/*Espressif* device)")
    parser.add_argument("--no-flash", action="store_true", help="only reset the board and check it")
    parser.add_argument("--rom", action="store_true", help="the board waits in ROM download mode")
    parser.add_argument("--fresh", action="store_true", help="erase the saved settings while flashing")
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
