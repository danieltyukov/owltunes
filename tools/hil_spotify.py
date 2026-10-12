#!/usr/bin/env python3
"""Drive the Spotify runtime on a linked board with your own Spotify account. Opt-in only.

This changes what your Spotify account is doing: it pauses and resumes playback, skips a track and
back, and moves the volume and puts it back. It likes a track that is not in Liked Songs and unlikes
it again; a track that is already liked is only liked again, so its place in Liked Songs should
stay. When a check fails or you press Ctrl-C, it puts back what it changed where it can (device,
volume, the like, playing or paused) and prints a "left changed:" line for anything it could not. It
refuses to run without --real-account. Link the board first (tools/owl_login.py) and start playing
something on a Spotify device.

  tools/hil_spotify.py --real-account               the checks above
  tools/hil_spotify.py --real-account --transfer    also move playback to another device and back
  tools/hil_spotify.py --real-account --idle        also pause and leave the owl alone for 16
                                                    minutes, long enough for Spotify to close the
                                                    idle connection, then check that play goes
                                                    through on a new one (play on a computer or a
                                                    speaker: an idle phone drops off Spotify's
                                                    device list)

Console logs go to build/hil-spotify/console.log; access tokens never appear there, and the script
checks that at the end.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from owl_serial import Board, BoardError, Message, find_port, parse_line, wait_online  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORK = ROOT / "build" / "hil-spotify"
FINAL_STATES = ("done", "failed", "refused")
AWAKE_S = 5 * 60  # console activity keeps the owl polling for this long (AWAKE_MS in spotify_task.c)
SERVER_KEEP_ALIVE_S = 610  # api.spotify.com closed an idle HTTP/1.1 connection after 610 s (11 Oct 2026)
CONNECTION_IDLE_S = 11 * 60  # how long the connection sits unused in the --idle check
RECONNECT_LOG = "spotify_http: the kept-alive connection was closed; reconnecting"
# Words that only a token or the code around one would print, and long base64url runs (P24).
TOKEN_LEAK = re.compile(r"access_token|refresh_token|Bearer|[A-Za-z0-9_-]{80,}")


class Failure(Exception):
    pass


def check(condition: bool, what: str) -> None:
    if not condition:
        raise Failure(what)
    print(f"ok - {what}", flush=True)


def volume_target(current: int) -> int:
    """A volume ten points away from current that stays within 0 to 100."""
    return current - 10 if current >= 10 else current + 10


def other_device(devices: list[Message], current_id: str) -> Message | None:
    """The first device that is not playing now and accepts commands."""
    for device in devices:
        if device.get("id") != current_id and not device.get("restricted"):
            return device
    return None


def like_order(liked: bool) -> tuple[str, ...]:
    """Commands that end where the library started. A liked track is only liked again (P17):
    unliking it and liking it back would move it to the top of Liked Songs."""
    return ("like",) if liked else ("like", "unlike")


def reconnected(lines: list[str]) -> bool:
    """The transport logged that it found the kept-alive connection closed and opened a new one."""
    return any(parse_line(line) is None and RECONNECT_LOG in line for line in lines)


def token_leaks(text: str) -> list[str]:
    """Everything in text that looks like an access or refresh token, or code printing one."""
    return TOKEN_LEAK.findall(text)


def run(board: Board, text: str, timeout: float = 20.0) -> Message:
    """Type a command and return its last cmd line: done, failed or refused."""
    return board.wait_event("cmd", timeout=timeout, since=board.type(text),
                            where=lambda m: m.get("state") in FINAL_STATES)


def run_ok(board: Board, text: str, what: str) -> int:
    """Run a command that must succeed. Returns the mark from which its confirming poll arrives."""
    since = board.mark()
    result = run(board, text)
    outcome = f"{result.get('state')} {result.get('error', '')}".strip()
    check(result.get("state") == "done", f"{what} ({text}: {outcome})")
    return since


def player_after(board: Board, since: int, what: str, condition, timeout: float = 20.0) -> Message:
    """The first player line since the mark that meets condition. 20 s covers one poll at the paused
    rate (15 s) when the confirming poll still saw the old state."""
    try:
        player = board.wait_event("player", timeout=timeout, since=since, where=condition)
    except BoardError:
        raise Failure(f"{what}: no matching playback state within {timeout:.0f} s") from None
    print(f"ok - {what}", flush=True)
    return player


def answer(board: Board, text: str, events: tuple[str, ...], timeout: float = 15.0) -> Message:
    """The first line of one of these events after typing text (a refusal is a cmd line)."""
    since = board.type(text)
    return board.wait(lambda line: m if (m := parse_line(line)) is not None and m.get("event") in events else None,
                      timeout, f"an answer to {text}", since)


def wait_active(board: Board, timeout: float = 90.0) -> Message:
    """Ask auth until the runtime is active (linked, online, clock checked) and holds a token. Right
    after the start the runtime refuses (offline) or has no token yet (the api line waits for one)."""
    deadline = time.monotonic() + timeout
    while True:
        reply = answer(board, "auth", ("auth", "cmd"))
        if reply.get("event") == "auth" and reply.get("state") == "ok":
            return reply
        if reply.get("error") in ("not_linked", "logged_out"):
            raise Failure(f"the owl has no usable Spotify login ({reply['error']}): link it with tools/owl_login.py")
        if time.monotonic() > deadline:
            raise Failure(f"the Spotify runtime did not get an access token ({reply.get('error')})")
        time.sleep(2)


def current_player(board: Board, timeout: float = 30.0) -> Message:
    """Ask for the playback state until the first poll has filled it in."""
    deadline = time.monotonic() + timeout
    while True:
        player = answer(board, "status", ("player", "cmd"))
        if player.get("event") == "player" and player.get("status") != "unknown":
            return player
        if time.monotonic() > deadline:
            raise Failure(f"the owl never read the playback state ({player.get('error', 'unknown')})")
        time.sleep(2)


def list_devices(board: Board) -> list[Message]:
    """The device lines of one devices answer. While Spotify may not be called the owl refuses the
    command with a cmd line instead (Task 15)."""
    since = board.type("devices")

    def match(line: str) -> Message | None:
        m = parse_line(line)
        if m is None:
            return None
        if m.get("event") == "devices" and m.get("state") in ("done", "failed"):
            return m
        return m if m.get("event") == "cmd" and m.get("cmd") == "devices" and m.get("state") == "refused" else None

    done = board.wait(match, 20, "the device list", since)
    check(done.get("event") == "devices" and done.get("state") == "done",
          f"the device list arrives ({done.get('error', 'ok')})")
    end = board.mark()
    return [m for line in board.lines[since:end] if (m := parse_line(line)) is not None and m.get("event") == "device"]


class Account:
    """What the test changed on the account and has not put back yet, for restore()."""

    def __init__(self) -> None:
        self.start: Message | None = None  # the playback state before the first change
        self.first_uri: str | None = None  # set when next is sent, cleared when prev brought it back
        self.liked_uri: str | None = None  # a track the test liked that was not in Liked Songs
        self.volume: int | None = None  # the volume to put back
        self.moved = False  # playback may be on another device


def like_checks(board: Board, account: Account, since: int, uri: str) -> None:
    """Like (and unlike) the first track, back after next and prev, as like_order says. The like state
    is the one Spotify gave for that track, and the track has just started, so it cannot end during
    the check."""
    try:
        player = board.wait_event("player", timeout=20, since=since,
                                  where=lambda m: m.get("uri") == uri and
                                  (isinstance(m.get("liked"), bool) or m.get("kind") != "track"))
    except BoardError:
        print("note - like not checked: the owl did not read the like state of the track", flush=True)
        return
    if player.get("kind") != "track" or not isinstance(player.get("liked"), bool):
        print(f"note - like not checked: a {player.get('kind')} whose like state is {player.get('liked')}", flush=True)
        return
    for command in like_order(player["liked"]):
        want = command == "like"
        if command == "like" and not player["liked"]:
            account.liked_uri = uri  # before sending: a like that timed out may still have happened
        since = run_ok(board, command, f"{command} goes through")
        after = player_after(board, since, f"the owl shows the track {'in' if want else 'out of'} Liked Songs",
                             lambda m, want=want: m.get("liked") is want or m.get("uri") != uri)
        if after.get("uri") != uri:
            raise Failure(f"the track changed during the like check: look at {uri} in Liked Songs")
        if command == "unlike":
            account.liked_uri = None


def back_to_first(board: Board, account: Account, first: str, skipped: str) -> int:
    """Send prev until the first track plays again. prev restarts the current track instead when it
    has played for a few seconds, so a second prev may be needed. Returns the mark of the last one."""
    for attempt in ("previous goes through", "previous goes through again (the first one restarted the track)"):
        since = run_ok(board, "prev", attempt)
        try:
            back = board.wait_event("player", timeout=12, since=since, where=lambda m: m.get("uri") != skipped)
        except BoardError:
            continue  # still on the skipped track
        if back.get("uri") != first:
            raise Failure(f"prev went to {back.get('uri')}, not back to {first}")
        account.first_uri = None
        print("ok - the first track plays again", flush=True)
        return since
    raise Failure(f"prev did not go back from {skipped} to {first}")


def idle_check(board: Board) -> None:
    """P9: leave the kept-alive connection unused for longer than Spotify keeps it, then check that the
    next command goes out on a new connection. Paused and with no console activity the owl does not
    poll at all (spec 9.4), so nothing may be typed during the wait."""
    since = run_ok(board, "pause", "paused before the idle wait")
    player_after(board, since, "Spotify reports it paused", lambda m: m.get("status") == "paused")
    total = AWAKE_S + CONNECTION_IDLE_S
    print(f"Leaving the owl alone for {total // 60} minutes (it polls for the first {AWAKE_S // 60})...", flush=True)
    time.sleep(total)
    since = board.mark()
    result = run(board, "play", timeout=40)
    reconnect = reconnected(board.lines[since:board.mark()])
    outcome = f"{result.get('state')} {result.get('error', '')}".strip()
    check(result.get("state") == "done", f"a command after a long idle still goes through (play: {outcome})")
    if not reconnect:
        raise Failure(f"no '{RECONNECT_LOG}' line: Spotify kept the connection open for "
                      f"{CONNECTION_IDLE_S // 60} idle minutes, so the reconnect was not checked")
    print("ok - it went out on a new connection", flush=True)
    player_after(board, since, "Spotify reports it playing", lambda m: m.get("status") == "playing")


def playback_checks(board: Board, args: argparse.Namespace, account: Account) -> None:
    try:
        hello = wait_online(board)
    except BoardError as err:
        raise Failure(str(err)) from None
    check(hello.get("linked") is True and hello.get("ip", "") != "", "the owl is linked and online")
    auth = wait_active(board)
    check(60 < auth.get("expires_in_s", 0) <= 3600,
          f"the owl holds a valid access token ({auth.get('expires_in_s')} s left)")
    start = current_player(board)
    if start.get("status") == "no_device":
        print("Start playing something on a Spotify device; waiting up to two minutes...", flush=True)
        deadline = time.monotonic() + 120
        while (start := current_player(board)).get("status") == "no_device":
            if time.monotonic() > deadline:
                raise Failure("no Spotify device became active")
            time.sleep(5)
    check(start.get("link") == "api", f"the Web API is reachable ({start.get('device')}, {start.get('status')})")
    devices = list_devices(board)
    check(any(d.get("id") == start.get("device_id") for d in devices),
          f"{len(devices)} device(s), the active one among them")
    account.start = start  # from here on restore() puts back what the checks change

    if start.get("status") == "paused":  # Spotify refuses to pause a paused player
        since = run_ok(board, "play", "play goes through")
        player_after(board, since, "Spotify reports it playing", lambda m: m.get("status") == "playing")
    since = run_ok(board, "pause", "pause goes through")
    player_after(board, since, "Spotify reports it paused", lambda m: m.get("status") == "paused")
    since = run_ok(board, "play", "play goes through")
    playing = player_after(board, since, "Spotify reports it playing", lambda m: m.get("status") == "playing")
    account.first_uri = str(playing.get("uri"))
    since = run_ok(board, "next", "next goes through")
    skipped = player_after(board, since, "the track changes", lambda m: m.get("uri") != playing.get("uri"))
    since = back_to_first(board, account, str(playing.get("uri")), str(skipped.get("uri")))
    like_checks(board, account, since, str(playing.get("uri")))

    volume = start.get("volume")
    if start.get("supports_volume") is False:
        refused = run(board, "vol 50")
        check(refused.get("error") == "volume_unsupported", "a device that refuses volume changes is not asked")
    elif volume is None or not start.get("supports_volume"):
        print("note - volume not checked: Spotify does not say what it is now, so it could not be put back", flush=True)
    else:
        target = volume_target(int(volume))
        account.volume = int(volume)
        since = run_ok(board, f"vol {target}", "volume goes through")
        player_after(board, since, "Spotify reports the new volume", lambda m: m.get("volume") == target)
        run_ok(board, f"vol {volume}", "the volume is put back")
        account.volume = None

    if args.transfer:
        target = other_device(devices, str(start.get("device_id")))
        if target is None:
            print("note - transfer not checked: no other device to move to", flush=True)
        else:
            account.moved = True
            since = run_ok(board, f"transfer {target['n']}", f"transfer to {target.get('name')} goes through")
            player_after(board, since, "playback moves", lambda m: m.get("device_id") == target.get("id"))
            since = run_ok(board, f"transfer {start.get('device_id')}", "transfer back goes through")
            player_after(board, since, "playback moves back", lambda m: m.get("device_id") == start.get("device_id"))
            account.moved = False

    if args.idle:
        idle_check(board)


def attempt(board: Board, text: str) -> bool:
    """Send a command while putting things back: True when Spotify accepted it. Never raises."""
    try:
        return run(board, text).get("state") == "done"
    except (Failure, BoardError):
        return False


def restore(board: Board, account: Account) -> list[str]:
    """Put back what the checks changed and have not put back themselves, after a failure, Ctrl-C or
    a run that ended in another state than it started. Never unlikes a track that started liked (P17).
    Prints and returns one line for each thing left changed."""
    start = account.start
    if start is None:
        return []
    left = []
    try:
        now: Message = current_player(board, timeout=10)
    except (Failure, BoardError):
        now = {}
    if account.moved and now.get("device_id") != start.get("device_id"):
        if attempt(board, f"transfer {start.get('device_id')}"):
            print(f"put back: playback on {start.get('device')}", flush=True)
        else:
            left.append(f"playback on {now.get('device', 'another device')} (was {start.get('device')})")
    if account.volume is not None:
        if attempt(board, f"vol {account.volume}"):
            print(f"put back: volume {account.volume}", flush=True)
        else:
            left.append(f"volume {now.get('volume', 'unknown')} (was {account.volume})")
    if account.liked_uri is not None:
        if now.get("uri") == account.liked_uri and attempt(board, "unlike"):
            print(f"put back: {account.liked_uri} out of Liked Songs", flush=True)
        else:
            left.append(f"{account.liked_uri} is in Liked Songs (it was not)")
    if account.first_uri is not None and now.get("uri") != account.first_uri:
        left.append(f"track {now.get('uri', 'unknown')} (was {account.first_uri})")
    was = start.get("status")
    if now.get("status") != was:
        command = "play" if was == "playing" else "pause"
        if not (was in ("playing", "paused") and now and attempt(board, command)):
            left.append(f"playback {now.get('status', 'unknown')} (was {was})")
        else:
            print(f"put back: playback {was}", flush=True)
    for line in left:
        print(f"left changed: {line}", flush=True)
    return left


def checks_and_restore(board: Board, args: argparse.Namespace) -> None:
    """playback_checks, then restore() whatever happened; anything left changed fails the run."""
    account = Account()
    try:
        playback_checks(board, args, account)
    finally:
        left = restore(board, account)
    if left:
        raise Failure(f"{len(left)} thing(s) left changed on the account (see above)")


def log_checks(board: Board, log: pathlib.Path) -> None:
    """What the brief asks the owner to report, from the lines of this run."""
    messages = [m for line in board.lines[:board.mark()] if (m := parse_line(line)) is not None]
    count = {name: sum(1 for m in messages if m.get("event") == name) for name in ("player", "cmd")}
    print(f"note - {count['player']} player and {count['cmd']} cmd lines", flush=True)
    limited = [m for m in messages if m.get("event") == "api" and m.get("state") in ("rate_limited", "quota")]
    check(not limited, "no api line said rate_limited or quota")
    check(not token_leaks(log.read_text(encoding="utf-8")), f"no token in {log.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--real-account", action="store_true", help="agree to control your own Spotify playback")
    parser.add_argument("--port", help="serial port (default: the one /dev/serial/by-id/*Espressif* device)")
    parser.add_argument("--transfer", action="store_true", help="also move playback to another device and back")
    parser.add_argument("--idle", action="store_true", help="also check a command after a long idle (16 minutes)")
    args = parser.parse_args()
    if not args.real_account:
        print("This test controls your real Spotify playback. Run it with --real-account.", file=sys.stderr)
        return 2
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
    try:
        board = Board(find_port(args.port), log)  # opening the port restarts the Nano ESP32
        checks_and_restore(board, args)
        log_checks(board, log)
    except (Failure, BoardError, KeyboardInterrupt) as err:
        print(f"FAIL - {str(err) or 'interrupted'} (console log in {log})", file=sys.stderr)
        if token_leaks(log.read_text(encoding="utf-8")):
            print(f"FAIL - something in {log} looks like a token: delete the log", file=sys.stderr)
        return 130 if isinstance(err, KeyboardInterrupt) else 1
    finally:
        if board is not None:
            board.close()
    print("Spotify hardware test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
