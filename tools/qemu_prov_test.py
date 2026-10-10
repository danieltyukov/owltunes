#!/usr/bin/env python3
"""Drive the real firmware in QEMU over its serial console and check the setup protocol.

Run after `tools/firmware.sh build` with ESP-IDF v6.1 activated (the script switches to the
ESP-IDF Python by itself):
  tools/qemu_prov_test.py          automatic checks, including a real HTTPS call to Spotify
  tools/qemu_prov_test.py --link   log in to your own Spotify app for real (see docs/setup-guide.md)
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import queue
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILD = ROOT / "build" / "firmware"
WORK = ROOT / "build" / "qemu-prov"
PREFIX = "@owl "
FAKE_CLIENT = "0123456789abcdef0123456789abcdef"
PAGES_REDIRECT = "https://danieltyukov.github.io/owltunes/callback/"
QEMU_IP = "10.0.2.15"


class Failure(Exception):
    pass


def check(condition: bool, what: str) -> None:
    if not condition:
        raise Failure(what)
    print(f"ok - {what}", flush=True)


def idf_python() -> str:
    """The interpreter the build was configured with; idf.py refuses to run under another one."""
    env = os.environ.get("IDF_PYTHON_ENV_PATH")
    return str(pathlib.Path(env, "bin", "python")) if env else sys.executable


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def make_flash_image(path: pathlib.Path) -> None:
    """Merge the build into a blank 16 MB image, the way idf.py qemu does."""
    if not (BUILD / "flash_args").exists():
        raise Failure("no firmware build: run tools/firmware.sh build first")
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [idf_python(), "-m", "esptool", "--chip=esp32s3", "merge-bin", f"--output={path}",
         "--pad-to-size=16MB", "@flash_args"],
        cwd=BUILD, check=True, stdout=subprocess.DEVNULL)


class Owl:
    """One QEMU run. Every console line is kept, so nothing printed before a wait is missed."""

    def __init__(self, flash: pathlib.Path, http_port: int, log: pathlib.Path):
        idf_py = pathlib.Path(os.environ["IDF_PATH"]) / "tools" / "idf.py"
        nic = f"-nic user,model=open_eth,hostfwd=tcp:127.0.0.1:{http_port}-:80"
        self.http_port = http_port
        self.lines: list[str] = []
        self.fresh: queue.Queue[str] = queue.Queue()
        self.next_id = 1
        self.log = log.open("w")
        self.proc = subprocess.Popen(
            [idf_python(), str(idf_py), "-C", "firmware", "-B", "build/firmware", "qemu", "--graphics",
             "--flash-file", str(flash), "--qemu-extra-args", nic],
            cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env={**os.environ, "SDL_VIDEODRIVER": "dummy"}, start_new_session=True)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        assert self.proc.stdout is not None
        for raw in self.proc.stdout:
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            self.log.write(line + "\n")
            self.log.flush()
            self.fresh.put(line)

    def mark(self) -> int:
        """Position after every line received so far; pass it as since= to wait for newer lines only."""
        while True:
            try:
                self.lines.append(self.fresh.get_nowait())
            except queue.Empty:
                return len(self.lines)

    def _wait(self, match, timeout: float, what: str, since: int = 0):
        for line in self.lines[since:]:
            found = match(line)
            if found is not None:
                return found
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                line = self.fresh.get(timeout=0.2)
            except queue.Empty:
                if self.proc.poll() is not None:
                    raise Failure(f"QEMU exited while waiting for {what}")
                continue
            self.lines.append(line)
            found = match(line)
            if found is not None:
                return found
        raise Failure(f"timed out after {timeout:.0f} s waiting for {what}")

    @staticmethod
    def _message(line: str):
        if not line.startswith(PREFIX):
            return None
        try:
            msg = json.loads(line[len(PREFIX):])
        except json.JSONDecodeError:
            return None
        return msg if isinstance(msg, dict) else None

    def wait_log(self, text: str, timeout: float = 90) -> str:
        return self._wait(lambda line: line if text in line else None, timeout, repr(text))

    def wait_event(self, event: str, state: str | None = None, timeout: float = 60, since: int = 0) -> dict:
        def match(line: str):
            msg = self._message(line)
            if msg and msg.get("event") == event and (state is None or msg.get("state") == state):
                return msg
            return None
        return self._wait(match, timeout, f"event {event} {state or ''}".strip(), since)

    def send(self, cmd: str, timeout: float = 20, **params) -> dict:
        req_id = self.next_id
        self.next_id += 1
        line = PREFIX + json.dumps({"id": req_id, "cmd": cmd, **params}, separators=(",", ":")) + "\n"
        assert self.proc.stdin is not None
        self.proc.stdin.write(line.encode())
        self.proc.stdin.flush()

        def match(text: str):
            msg = self._message(text)
            return msg if msg and msg.get("id") == req_id and "ok" in msg else None
        return self._wait(match, timeout, f"a reply to {cmd}")

    def stop(self) -> None:
        if self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGTERM)
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
        self.log.close()


def authorize_params(owl: Owl) -> dict[str, str]:
    reply = owl.send("spotify_begin")
    check(reply.get("ok") is True, "spotify_begin returns an authorize URL")
    url = urllib.parse.urlsplit(reply["authorize_url"])
    check(url.scheme == "https" and url.netloc == "accounts.spotify.com" and url.path == "/authorize",
          "the authorize URL points at accounts.spotify.com/authorize")
    return dict(urllib.parse.parse_qsl(url.query))


def run_checks(flash: pathlib.Path) -> None:
    owl = Owl(flash, free_port(), WORK / "run1.log")
    try:
        owl.wait_log("OWL_BOOT_OK")
        hello = owl.send("hello")
        check(hello.get("ok") is True and hello.get("protocol") == 1, "hello answers with protocol 1")
        check(re.fullmatch(r"OwlTunes-[0-9A-F]{4}", hello.get("name", "")) is not None, "the owl has a name")
        check(hello.get("linked") is False, "a fresh owl is not linked")
        up = owl.wait_event("network", "up")
        check(up.get("ip") == QEMU_IP, "QEMU Ethernet comes up with the slirp address")
        check(owl.send("hello").get("setup") == "needs_spotify", "with a network the owl needs Spotify")

        check(owl.send("wifi_add", ssid="Home", password="short").get("error") == "bad_password",
              "a short Wi-Fi password is refused")
        check(owl.send("wifi_add", ssid="Home", password="password1").get("ok") is True, "a Wi-Fi network is saved")
        check(owl.send("spotify_client", client_id="ABC", redirect_uri=PAGES_REDIRECT).get("error") == "bad_client_id",
              "a malformed client ID is refused")
        check(owl.send("spotify_client", client_id=FAKE_CLIENT, redirect_uri=PAGES_REDIRECT).get("ok") is True,
              "the client ID is saved")

        params = authorize_params(owl)
        check(params.get("client_id") == FAKE_CLIENT and params.get("redirect_uri") == PAGES_REDIRECT,
              "the authorize URL carries the client ID and redirect URI")
        check(params.get("code_challenge_method") == "S256" and len(params.get("code_challenge", "")) == 43,
              "the authorize URL carries an S256 PKCE challenge")
        check("user-modify-playback-state" in params.get("scope", "").split(" "), "the scopes include playback control")
        state = params.get("state", "")
        check(state.endswith("." + QEMU_IP), "the state carries the owl's address for the LAN fallback")

        wrong = state[:-1] + ("A" if state[-1] != "A" else "B")
        check(owl.send("spotify_code", code="AQDfake", state=wrong).get("error") == "bad_state",
              "a code with the wrong state is refused")
        check(owl.send("spotify_code", code="AQD&x=1", state=state).get("error") == "bad_code",
              "a code with unsafe characters is refused")
        check(owl.send("spotify_code", code="AQDfake", state=state).get("accepted") is True,
              "a code with the right state is accepted")
        owl.wait_event("spotify", "linking")
        failed = owl.wait_event("spotify", "failed", timeout=90)
        if failed.get("error") == "network":
            raise Failure("QEMU could not reach accounts.spotify.com (is this machine online?)")
        check(failed.get("error") in ("invalid_client", "invalid_grant"),
              f"Spotify answered the HTTPS token request ({failed.get('error')})")
        extra_checks(owl)
    finally:
        owl.stop()

    owl = Owl(flash, free_port(), WORK / "run2.log")
    try:
        owl.wait_log("OWL_BOOT_OK")
        owl.wait_event("network", "up")
        hello = owl.send("hello")
        check(hello.get("networks") == ["Home"] and hello.get("client_id") == FAKE_CLIENT,
              "the Wi-Fi network and client ID survive a reboot")
        check(hello.get("setup") == "needs_spotify", "after the failed login the owl still needs Spotify")
    finally:
        owl.stop()


def extra_checks(owl: Owl) -> None:
    """Checks added by later tasks."""


def run_link(flash: pathlib.Path, client_id: str, redirect_uri: str, http_port: int) -> None:
    owl = Owl(flash, http_port, WORK / "link.log")
    try:
        owl.wait_log("OWL_BOOT_OK")
        owl.wait_event("network", "up")
        check(owl.send("spotify_client", client_id=client_id, redirect_uri=redirect_uri).get("ok") is True,
              "your client ID is saved")
        reply = owl.send("spotify_begin")
        print("\nOpen this address, log in, and paste the address Spotify sends you back to:\n")
        print(reply["authorize_url"] + "\n", flush=True)
        back = urllib.parse.urlsplit(input("Address after login: ").strip())
        params = dict(urllib.parse.parse_qsl(back.query))
        check("code" in params, "the address carries a login code")
        check(owl.send("spotify_code", code=params["code"], state=params.get("state", "")).get("accepted") is True,
              "the owl accepts the code")
        owl.wait_event("spotify", "linked", timeout=90)
        hello = owl.send("hello")
        check(hello.get("linked") is True and hello.get("setup") == "ready",
              "the owl is linked to your Spotify account")
    finally:
        owl.stop()
    owl = Owl(flash, http_port, WORK / "link2.log")
    try:
        owl.wait_log("OWL_BOOT_OK")
        owl.wait_event("spotify", "linked", timeout=120)
        hello = owl.send("hello")
        owl.mark()
        check(not any('"logged_out"' in line for line in owl.lines) and hello.get("setup") == "ready",
              "after a reboot the saved login still works (refresh token accepted)")
    finally:
        owl.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--link", action="store_true", help="log in to your own Spotify app")
    parser.add_argument("--client-id", default=os.environ.get("OWL_SPOTIFY_CLIENT_ID", ""))
    parser.add_argument("--redirect-uri", default=PAGES_REDIRECT)
    parser.add_argument("--http-port", type=int, default=18080,
                        help="host port forwarded to the owl's port 80 (--link only)")
    args = parser.parse_args()
    if "IDF_PATH" not in os.environ:
        print("ESP-IDF v6.1 is not activated (IDF_PATH is not set)", file=sys.stderr)
        return 2
    try:
        import esptool  # noqa: F401  (only the ESP-IDF Python has it)
    except ImportError:
        idf_python = pathlib.Path(os.environ.get("IDF_PYTHON_ENV_PATH", "/nonexistent"), "bin", "python")
        if idf_python.exists() and pathlib.Path(sys.executable) != idf_python:
            os.execv(idf_python, [str(idf_python), __file__, *sys.argv[1:]])
        print("cannot find the ESP-IDF Python (activate ESP-IDF first)", file=sys.stderr)
        return 2
    shutil.rmtree(WORK, ignore_errors=True)
    flash = WORK / "flash.bin"
    try:
        make_flash_image(flash)
        if args.link:
            if not re.fullmatch(r"[0-9a-f]{32}", args.client_id):
                raise Failure("--link needs --client-id with your 32-character Spotify client ID")
            run_link(flash, args.client_id, args.redirect_uri, args.http_port)
        else:
            run_checks(flash)
    except Failure as err:
        print(f"FAIL - {err} (console logs in {WORK})", file=sys.stderr)
        return 1
    print("QEMU provisioning test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
