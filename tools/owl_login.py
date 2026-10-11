#!/usr/bin/env python3
"""Link a board on USB to your Spotify account from this computer, without the setup page.

The script serves http://127.0.0.1:<port>/callback on this computer, saves your client ID on the
owl with that address as the redirect URI, prints the Spotify login address and hands the code
Spotify sends back to the owl over USB. The owl exchanges the code itself (PKCE: no client secret,
and the tokens never leave the owl). Then it resets the owl and waits for the saved login to pass
its check at boot. Add the redirect URI to your Spotify app first (docs/dev-board-nano-esp32.md).

  tools/owl_login.py                     client ID from OWL_SPOTIFY_CLIENT_ID or private/hil.env
  tools/owl_login.py --open              also open the login page in the default browser
  tools/owl_login.py --http-port 8766    another local port (add its redirect URI to the app too)

Opening the serial port restarts the Nano ESP32, so the script opens it once, waits for the owl to
start and join its Wi-Fi, and keeps the port open until the end. Run it in your own terminal: it
prints the login address, which carries your client ID. The console log
(build/owl-login/console.log) shows the client ID as <redacted>, and the script fails if anything
in it looks like a token.
"""

from __future__ import annotations

import argparse
import http.server
import os
import pathlib
import queue
import re
import sys
import threading
import time
import urllib.parse
import webbrowser

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from owl_serial import Board, BoardError, Message, find_port, load_env_file  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORK = ROOT / "build" / "owl-login"
DEFAULT_HTTP_PORT = 8765
LOGIN_TIMEOUT_S = 600  # the owl keeps a login open for 10 minutes
ONLINE_TIMEOUT_S = 90  # boot, then join the saved Wi-Fi network
EXCHANGE_TIMEOUT_S = 90
BOOT_CHECK_TIMEOUT_S = 90
AUTHORIZE_PREFIX = "https://accounts.spotify.com/authorize?"
PAGE = (b"<!doctype html><meta charset=utf-8><title>OwlTunes</title>"
        b"<p>Your owl got the answer from Spotify. You can close this tab.</p>")
TOKEN_NAMES = ("access_token", "refresh_token")
TOKEN_RUN = re.compile(r"[A-Za-z0-9_-]{80,}")  # Spotify tokens are long base64url strings


class Failure(Exception):
    pass


def check(condition: bool, what: str) -> None:
    if not condition:
        raise Failure(what)
    print(f"ok - {what}", flush=True)


def redirect_uri(port: int) -> str:
    return f"http://127.0.0.1:{port}/callback"


def normalize_client_id(text: str) -> str | None:
    """The client ID as Spotify shows it (32 hex characters, any case, spaces around); None if not."""
    value = text.strip().lower()
    return value if re.fullmatch(r"[0-9a-f]{32}", value) else None


def read_callback(path: str) -> dict[str, str]:
    """code, state and error from a request path; empty for anything but /callback."""
    url = urllib.parse.urlsplit(path)
    if url.path != "/callback":
        return {}
    params = dict(urllib.parse.parse_qsl(url.query))
    return {key: params[key] for key in ("code", "state", "error") if key in params}


def serve_callback(port: int, answers: queue.Queue[dict[str, str]]) -> http.server.HTTPServer:
    """Listen on 127.0.0.1 only. The page never repeats anything from the request. Each connection
    gets its own thread and at most 10 s, so a stray one cannot hold up Spotify's redirect."""

    class Handler(http.server.BaseHTTPRequestHandler):
        timeout = 10  # seconds a connection may stay silent

        def do_GET(self) -> None:  # noqa: N802 (the http.server API)
            answer = read_callback(self.path)
            if answer:
                answers.put(answer)
            self.send_response(200 if answer else 404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(PAGE if answer else b"")

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass  # the query holds the login code: keep it out of the terminal

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def wait_answer(answers: queue.Queue[dict[str, str]], state: str, timeout: float) -> dict[str, str]:
    """Spotify's answer for this login. A callback with another state (a reloaded tab from an
    earlier login, another page) is skipped; the owl would refuse its code anyway."""
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        try:
            if remaining <= 0:
                raise queue.Empty
            answer = answers.get(timeout=remaining)
        except queue.Empty:
            raise Failure(f"no answer from Spotify within {timeout:.0f} s") from None
        if answer.get("state") == state:
            return answer
        print("note - skipped a callback that belongs to another login", flush=True)


def token_leaks(text: str) -> list[str]:
    """Why text may hold a Spotify token: a token field name, or a run of 80 or more base64url
    characters. The reasons never repeat what they found."""
    reasons = []
    for number, line in enumerate(text.splitlines(), start=1):
        reasons += [f"line {number} names {name}" for name in TOKEN_NAMES if name in line]
        reasons += [f"line {number} has a run of {len(m.group())} token-like characters"
                    for m in TOKEN_RUN.finditer(line)]
    return reasons


def client_id_from(args: argparse.Namespace) -> str:
    env = {**load_env_file(ROOT / "private" / "hil.env"), **os.environ}
    client_id = normalize_client_id(args.client_id or env.get("OWL_SPOTIFY_CLIENT_ID", ""))
    if client_id is None:
        raise Failure("give your Spotify app's client ID (--client-id, OWL_SPOTIFY_CLIENT_ID or private/hil.env)")
    return client_id


def wait_online(board: Board, timeout: float = ONLINE_TIMEOUT_S) -> Message:
    """hello once the owl has an address. The owl refuses to start a login while it is offline."""
    deadline = time.monotonic() + timeout
    while True:
        hello = board.hello()
        if hello.get("ip", ""):
            return hello
        if not hello.get("networks"):
            raise Failure("the owl has no Wi-Fi network saved: add one first (the setup page or "
                          "tools/hil_nano.py --wifi)")
        if time.monotonic() > deadline:
            raise Failure(f"the owl did not come online within {timeout:.0f} s")
        time.sleep(2)


def link(board: Board, client_id: str, port: int, open_browser: bool) -> None:
    hello = wait_online(board)
    print(f"ok - {hello.get('name')} is online at {hello.get('ip')}", flush=True)
    answers: queue.Queue[dict[str, str]] = queue.Queue()
    # Listen before saving the redirect URI: a port in use must not cost the owl its saved login.
    server = serve_callback(port, answers)
    try:
        uri = redirect_uri(server.server_address[1])
        reply = board.request("spotify_client", client_id=client_id, redirect_uri=uri)
        check(reply.get("ok") is True, f"the client ID is saved with the redirect URI {uri}")
        reply = board.request("spotify_begin")
        url = str(reply.get("authorize_url", ""))
        state = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query)).get("state", "")
        check(reply.get("ok") is True and url.startswith(AUTHORIZE_PREFIX) and state != "",
              f"the owl opened a login ({reply.get('error', 'ok')})")
        print(f"\nOpen this address and log in to Spotify:\n\n{url}\n", flush=True)
        if open_browser:
            webbrowser.open(url)
        answer = wait_answer(answers, state, LOGIN_TIMEOUT_S)
    finally:
        server.shutdown()
        server.server_close()
    if "error" in answer:
        raise Failure(f"Spotify did not log you in ({answer['error']})")
    since = board.mark()
    reply = board.request("spotify_code", code=answer.get("code", ""), state=answer.get("state", ""))
    check(reply.get("accepted") is True, f"the owl accepted the code from Spotify ({reply.get('error', 'ok')})")
    result = board.wait_event("spotify", timeout=EXCHANGE_TIMEOUT_S, since=since,
                              where=lambda m: m.get("state") in ("linked", "failed"))
    check(result.get("state") == "linked", f"the owl exchanged the code itself ({result.get('error', 'linked')})")
    hello = board.hello()
    check(hello.get("linked") is True and hello.get("setup") == "ready", "the login is saved on the owl")


def boot_check(board: Board) -> None:
    """After a reset the owl refreshes the saved login once it is online and reports it."""
    for attempt in (1, 2):
        since = board.reset()
        try:
            board.wait_boot(since=since)
            board.hello()
            result = board.wait_event("spotify", timeout=BOOT_CHECK_TIMEOUT_S, since=since,
                                      where=lambda m: m.get("state") in ("linked", "logged_out", "failed"))
        except BoardError:
            print(f"note - the boot check was not seen (attempt {attempt}); resetting again", flush=True)
            continue
        outcome = " ".join(str(result.get(key)) for key in ("state", "error") if result.get(key))
        check(result.get("state") == "linked",
              f"after a reset the saved login passes its check with Spotify ({outcome})")
        return
    raise Failure("the owl never reported its boot check; look at the console log")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", help="serial port (default: the one /dev/serial/by-id/*Espressif* device)")
    parser.add_argument("--client-id", help="your Spotify app's client ID")
    parser.add_argument("--http-port", type=int, default=DEFAULT_HTTP_PORT, help="local port for the callback")
    parser.add_argument("--open", action="store_true", help="open the login page in the default browser")
    args = parser.parse_args()
    try:
        import serial  # noqa: F401  (pyserial; the ESP-IDF Python has it)
    except ImportError:
        idf_python = pathlib.Path(os.environ.get("IDF_PYTHON_ENV_PATH", "/nonexistent"), "bin", "python")
        if idf_python.exists() and pathlib.Path(sys.executable) != idf_python:
            os.execv(idf_python, [str(idf_python), __file__, *sys.argv[1:]])
        print("cannot find pyserial (activate ESP-IDF v6.1 first)", file=sys.stderr)
        return 2
    WORK.mkdir(parents=True, exist_ok=True)
    log = WORK / "console.log"
    log.write_text("")
    board = None
    failed = None
    try:
        client_id = client_id_from(args)
        board = Board(find_port(args.port), log, redact=(client_id,))  # this restarts the Nano
        try:
            board.wait_boot()
        except BoardError:
            print("note - no boot line after opening the port; asking the owl directly", flush=True)
        link(board, client_id, args.http_port, args.open)
        boot_check(board)
    except (Failure, BoardError, OSError) as err:
        failed = str(err)
    finally:
        if board is not None:
            board.close()
    leaks = token_leaks(log.read_text(encoding="utf-8", errors="replace"))
    if leaks:
        failed = f"the console log may hold a token: {'; '.join(leaks)}"
    if failed is not None:
        print(f"FAIL - {failed} (console log in {log})", file=sys.stderr)
        return 1
    print("ok - no token reached the console log")
    print("The owl is linked to your Spotify account")
    return 0


if __name__ == "__main__":
    sys.exit(main())
