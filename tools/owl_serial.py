#!/usr/bin/env python3
"""Talk to an OwlTunes board over its USB console.

The console carries the firmware's log, @owl protocol lines (docs/provisioning-protocol.md) and the
developer console (docs/console.md). This module finds the board's port, resets the board, sends
lines and waits for answers. Every received line is kept, so nothing printed before a wait starts
is missed. tools/hil_nano.py, tools/owl_login.py and tools/hil_spotify.py build on it.
"""

from __future__ import annotations

import glob
import json
import pathlib
import queue
import re
import threading
import time
from typing import Any, Callable

PREFIX = "@owl "
PORT_GLOB = "/dev/serial/by-id/*Espressif*"
BOOT_MARKER = "OWL_BOOT_OK"  # the line the firmware logs when it has started
# A client ID is personal: logs in build/ must not show it, whichever script wrote them.
CLIENT_ID = re.compile(r'("client_id"\s*:\s*"|client_id=)[0-9A-Fa-f]{32}(?![0-9A-Fa-f])')

Message = dict[str, Any]


class BoardError(Exception):
    """The board did not answer as expected."""


def blocking_reads(fd: int) -> None:
    """Put VMIN back to its default of 1 before the port is closed. pyserial sets it to 0 and Linux
    keeps a tty's settings after it is closed; Chrome's Web Serial then takes an empty read for a
    lost device, and the setup page loses the owl."""
    import termios  # POSIX only, like the ports this module opens

    try:
        attrs = termios.tcgetattr(fd)
        attrs[6][termios.VMIN] = 1
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
    except termios.error:
        pass  # the board was unplugged: its next tty starts with the default


def parse_line(line: str) -> Message | None:
    """The JSON object of an @owl line; None for log lines and anything malformed."""
    if not line.startswith(PREFIX):
        return None
    try:
        msg = json.loads(line[len(PREFIX):])
    except json.JSONDecodeError:
        return None
    return msg if isinstance(msg, dict) else None


def redact_line(line: str, extra: tuple[str, ...] = ()) -> str:
    """line with every Spotify client ID shown as <redacted>, wherever the owl prints one (the
    "client_id" field of hello, client_id= in an authorize URL), and each text in extra too."""
    line = CLIENT_ID.sub(r"\1<redacted>", line)
    for text in extra:
        if text:
            line = line.replace(text, "<redacted>")
    return line


def find_port(explicit: str | None = None, pattern: str = PORT_GLOB) -> str:
    """explicit when given, else the one port whose /dev/serial/by-id name mentions Espressif.

    The by-id name stays the same when the board comes back as another ttyACM after a reset."""
    if explicit:
        return explicit
    found = sorted(glob.glob(pattern))
    if len(found) != 1:
        raise BoardError(f"expected one board at {pattern}, found {len(found)}: {found}")
    return found[0]


def load_env_file(path: pathlib.Path) -> dict[str, str]:
    """KEY=value lines from a private settings file such as private/hil.env; # starts a comment.
    A value in double quotes keeps the spaces at its ends (a Wi-Fi name can end with one)."""
    values: dict[str, str] = {}
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] == '"':
                    value = value[1:-1]
                values[key.strip()] = value
    return values


class Board:
    """One open console. A reader thread collects lines; waits look at everything since a mark."""

    def __init__(self, port: str, log: pathlib.Path | None = None, open_timeout: float = 20.0,
                 redact: tuple[str, ...] = ()):
        """The log file shows every client ID as <redacted> (redact_line), and also each text in
        redact. The lines kept in memory are unchanged, so waits still see them."""
        import serial  # only the hardware scripts need pyserial

        self._serial = serial
        self.port = port
        self.lines: list[str] = []
        self.next_id = 1
        self._fresh: queue.Queue[str] = queue.Queue()
        self._redact = tuple(text for text in redact if text)
        self._log = log.open("a", encoding="utf-8") if log is not None else None
        self._ser: Any = None
        self.open(open_timeout)  # on the Nano ESP32 this resets the board: see wait_boot()

    def open(self, timeout: float = 20.0) -> None:
        """Open the port, waiting up to timeout for it to appear (the board re-enumerates on reset)."""
        deadline = time.monotonic() + timeout
        while True:
            ser = self._serial.Serial()
            ser.port = self.port
            ser.baudrate = 115200
            ser.timeout = 0.2
            ser.dtr = False  # held low; the Nano ESP32 still resets when the port opens
            ser.rts = False
            try:
                ser.open()
                break
            except (OSError, self._serial.SerialException):
                if time.monotonic() > deadline:
                    raise BoardError(f"{self.port} did not appear within {timeout:.0f} s") from None
                time.sleep(0.2)
        self._ser = ser
        threading.Thread(target=self._read, args=(ser,), daemon=True).start()

    def _read(self, ser: Any) -> None:
        pending = b""
        while True:
            try:
                chunk = ser.read(512)
            except (OSError, TypeError, self._serial.SerialException):
                return  # unplugged, reset or closed; open() starts a new reader
            pending += chunk
            while b"\n" in pending:
                raw, pending = pending.split(b"\n", 1)
                line = raw.decode("utf-8", "replace").rstrip("\r")
                if self._log is not None:
                    self._log.write(redact_line(line, self._redact) + "\n")
                    self._log.flush()
                self._fresh.put(line)

    def close(self) -> None:
        if self._ser is not None:
            try:
                blocking_reads(self._ser.fd)
                self._ser.close()
            except (OSError, self._serial.SerialException):
                pass
            self._ser = None

    def reset(self, timeout: float = 20.0) -> int:
        """Reset the chip (RTS on USB-Serial/JTAG) and reopen the port. Returns the mark to wait from."""
        since = self.mark()
        self._ser.rts = True
        time.sleep(0.2)
        self._ser.rts = False
        self.close()
        time.sleep(1.0)  # let the old device node go before looking for the new one
        self.open(timeout)
        return since

    def wait_boot(self, timeout: float = 20.0, since: int = 0) -> int:
        """Wait for the firmware's boot line. Opening the port resets the Nano ESP32 (USB-Serial/JTAG
        restarted the chip on every open, 3 of 3 times, with DTR and RTS held low), so call this right
        after open() or reset(). Returns the position after the boot line."""
        self.wait(lambda line: True if BOOT_MARKER in line else None, timeout, "the boot line", since)
        return self.mark()

    def mark(self) -> int:
        """Position after every line received so far; pass it as since= to wait for newer lines."""
        while True:
            try:
                self.lines.append(self._fresh.get_nowait())
            except queue.Empty:
                return len(self.lines)

    def wait(self, match: Callable[[str], Any], timeout: float, what: str, since: int = 0) -> Any:
        self.mark()
        for line in self.lines[since:]:
            found = match(line)
            if found is not None:
                return found
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                line = self._fresh.get(timeout=0.2)
            except queue.Empty:
                continue
            self.lines.append(line)
            found = match(line)
            if found is not None:
                return found
        raise BoardError(f"timed out after {timeout:.0f} s waiting for {what}")

    def write_line(self, text: str) -> None:
        if self._ser is None:
            raise BoardError("the port is closed")
        self._ser.write((text + "\n").encode("utf-8"))
        self._ser.flush()

    def type(self, text: str) -> int:
        """Send a developer console line. Returns the mark to wait for its answer from."""
        since = self.mark()
        self.write_line(text)
        return since

    def request(self, cmd: str, timeout: float = 10.0, **params: Any) -> Message:
        """Send one @owl request and return its reply (which may say ok: false)."""
        req_id = self.next_id
        self.next_id += 1
        since = self.mark()
        self.write_line(PREFIX + json.dumps({"id": req_id, "cmd": cmd, **params}, separators=(",", ":")))

        def match(line: str) -> Message | None:
            msg = parse_line(line)
            return msg if msg is not None and msg.get("id") == req_id and "ok" in msg else None

        return self.wait(match, timeout, f"a reply to {cmd}", since)

    def hello(self, timeout: float = 30.0) -> Message:
        """hello, asked again every two seconds until the board answers (it may still be booting)."""
        deadline = time.monotonic() + timeout
        while True:
            try:
                return self.request("hello", timeout=2.0)
            except BoardError:
                if time.monotonic() > deadline:
                    raise BoardError(f"no hello reply within {timeout:.0f} s") from None

    def wait_event(self, event: str, state: str | None = None, timeout: float = 30.0, since: int = 0,
                   where: Callable[[Message], bool] | None = None) -> Message:
        def match(line: str) -> Message | None:
            msg = parse_line(line)
            if msg is None or msg.get("event") != event or (state is not None and msg.get("state") != state):
                return None
            return msg if where is None or where(msg) else None

        return self.wait(match, timeout, f"event {event} {state or ''}".strip(), since)

    def command(self, text: str, event: str, state: str | None = None, timeout: float = 10.0,
                where: Callable[[Message], bool] | None = None) -> Message:
        """Type a console command and return the first matching event it answers with."""
        return self.wait_event(event, state, timeout, self.type(text), where)
