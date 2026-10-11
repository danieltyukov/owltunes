import argparse
import io
import json
import pathlib
import queue
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import hil_spotify  # noqa: E402
from hil_spotify import like_order, other_device, reconnected, token_leaks, volume_target  # noqa: E402
from owl_serial import PREFIX, Board  # noqa: E402

TRACKS = ["spotify:track:aaa", "spotify:track:bbb"]


class FakeOwl(Board):
    """Answers console lines the way the runtime does, against a pretend Spotify account."""

    def __init__(self, liked=False, reconnects=True, fail=(), fail_once=(), prev_restarts=0, status="playing",
                 interrupt=False):
        self.lines = []
        self._fresh = queue.Queue()
        self.next_id = 1
        self.typed = []
        self.library = {TRACKS[0]} if liked else set()
        self.track = 0
        self.status = status
        self.fail = set(fail)  # commands Spotify always refuses
        self.fail_once = set(fail_once)  # commands refused the first time only
        self.prev_restarts = prev_restarts  # how many prevs restart the track instead of going back
        self.interrupt = interrupt  # Ctrl-C during the idle wait
        self.volume = 64
        self.device = "dev1"
        self.idle = False
        self.reconnects = reconnects

    def emit(self, **msg):
        self._fresh.put(PREFIX + json.dumps(msg, separators=(",", ":")))

    def player(self, liked=True):
        uri = TRACKS[self.track]
        self.emit(event="player", status=self.status, kind="track", uri=uri,
                  liked=(uri in self.library) if liked else None, device_id=self.device, device="Desk",
                  volume=self.volume, supports_volume=True, link="api")

    def write_line(self, text):
        if text.startswith(PREFIX):
            req = json.loads(text[len(PREFIX):])
            self.emit(id=req["id"], ok=True, linked=True, ip="192.168.1.5")
            return
        self.typed.append(text)
        verb, _, arg = text.partition(" ")
        if verb == "auth":
            self.emit(event="auth", state="ok", expires_in_s=3400)
        elif verb == "status":
            self.player()
        elif verb == "devices":
            self.emit(event="device", n=1, id="dev1", name="Desk", restricted=False)
            self.emit(event="device", n=2, id="dev2", name="Kitchen", restricted=False)
            self.emit(event="devices", state="done", count=2)
        else:
            name = {"vol": "volume", "prev": "previous"}.get(verb, verb)
            self.emit(event="cmd", state="queued", cmd=name)
            if text in self.fail or text in self.fail_once:
                self.fail_once.discard(text)
                self.emit(event="cmd", state="failed", cmd=name, error="network")
                self.player()
                return
            if self.idle and self.reconnects:
                self._fresh.put("I (999999) spotify_http: the kept-alive connection was closed; reconnecting")
            self.idle = False
            new_track = verb in ("next", "prev")
            if verb in ("play", "pause"):
                self.status = "playing" if verb == "play" else "paused"
            elif verb == "prev" and self.prev_restarts > 0:
                self.prev_restarts -= 1
            elif new_track:
                self.track = 1 if verb == "next" else 0
            elif verb == "vol":
                self.volume = int(arg)
            elif verb == "like":
                self.library.add(TRACKS[self.track])
            elif verb == "unlike":
                self.library.discard(TRACKS[self.track])
            elif verb == "transfer":
                self.device = "dev2" if arg == "2" else arg
            self.emit(event="cmd", state="done", cmd=name)
            self.player(liked=not new_track)
            if new_track:
                self.player()

    def sleep(self, seconds):
        if self.interrupt and seconds > hil_spotify.SERVER_KEEP_ALIVE_S:
            raise KeyboardInterrupt
        self.idle = self.idle or seconds > hil_spotify.SERVER_KEEP_ALIVE_S


_wait_event = Board.wait_event


def fast_wait_event(self, event, state=None, timeout=30.0, since=0, where=None):
    """Board.wait_event without the long waits for lines the fake will never send."""
    return _wait_event(self, event, state, min(timeout, 0.3), since, where)


class HelperTest(unittest.TestCase):
    def test_volume_target_stays_in_range(self):
        self.assertEqual(volume_target(64), 54)
        self.assertEqual(volume_target(10), 0)
        self.assertEqual(volume_target(3), 13)
        self.assertEqual(volume_target(100), 90)

    def test_other_device_skips_the_active_and_restricted_ones(self):
        devices = [
            {"n": 1, "id": "aaa", "restricted": False},
            {"n": 2, "id": "bbb", "restricted": True},
            {"n": 3, "id": "ccc", "restricted": False},
        ]
        self.assertEqual(other_device(devices, "aaa")["n"], 3)
        self.assertIsNone(other_device(devices[:2], "aaa"))

    def test_like_order_leaves_the_library_as_it_was(self):
        self.assertEqual(like_order(False), ("like", "unlike"))

    def test_a_liked_track_is_only_liked_again(self):
        # Unliking a track the owner liked and liking it again would move it in Liked Songs.
        self.assertEqual(like_order(True), ("like",))


class LogTest(unittest.TestCase):
    def test_the_transport_reconnect_line_counts(self):
        lines = ["I (100) spotify: queued",
                 "I (612345) spotify_http: the kept-alive connection was closed; reconnecting",
                 '@owl {"event":"cmd","state":"done","cmd":"play"}']
        self.assertTrue(reconnected(lines))
        self.assertFalse(reconnected([lines[0], lines[2]]))
        self.assertFalse(reconnected(['@owl {"event":"info","name":"the kept-alive connection was closed"}']))

    def test_a_clean_log_has_no_token_leaks(self):
        log = ('@owl {"event":"auth","state":"ok","expires_in_s":3412}\n'
               '@owl {"event":"device","n":1,"id":"0d1841b0976bae2a3a310dd74c0f3df354899bc8"}\n'
               "I (1234) owltunes: OWL_BOOT_OK board=nano_esp32 name=OwlTunes-7DF8\n")
        self.assertEqual(token_leaks(log), [])

    def test_token_names_and_long_base64url_runs_are_leaks(self):
        self.assertEqual(len(token_leaks('{"access_token":"x"}')), 1)
        self.assertEqual(len(token_leaks("refresh_token=y")), 1)
        self.assertEqual(len(token_leaks("Authorization: Bearer z")), 1)
        self.assertEqual(len(token_leaks("BQ" + "a1_-" * 20)), 1)
        self.assertEqual(token_leaks("x" * 79), [])


class PlaybackTest(unittest.TestCase):
    def checks(self, owl, raises=None, **flags):
        args = argparse.Namespace(**{"transfer": False, "idle": False, **flags})
        with mock.patch.object(hil_spotify.time, "sleep", owl.sleep), redirect_stdout(io.StringIO()) as out:
            if raises is None:
                hil_spotify.checks_and_restore(owl, args)
            else:
                with self.assertRaises(raises) as caught:
                    hil_spotify.checks_and_restore(owl, args)
                self.error = str(caught.exception)
        return out.getvalue()

    def test_a_track_not_in_liked_songs_is_liked_and_unliked(self):
        owl = FakeOwl(liked=False)
        self.checks(owl)
        self.assertEqual([t for t in owl.typed if "like" in t], ["like", "unlike"])
        self.assertEqual(owl.library, set())
        self.assertEqual(owl.volume, 64)

    def test_a_liked_track_is_never_unliked(self):
        owl = FakeOwl(liked=True)
        self.checks(owl)
        self.assertNotIn("unlike", owl.typed)
        self.assertIn("like", owl.typed)
        self.assertEqual(owl.library, {TRACKS[0]})

    def test_a_muted_device_is_put_back_to_zero(self):
        owl = FakeOwl()
        owl.volume = 0
        self.checks(owl)
        self.assertEqual([t for t in owl.typed if t.startswith("vol")], ["vol 10", "vol 0"])
        self.assertEqual(owl.volume, 0)

    def test_transfer_moves_playback_away_and_back(self):
        owl = FakeOwl()
        self.checks(owl, transfer=True)
        self.assertIn("transfer 2", owl.typed)
        self.assertEqual(owl.device, "dev1")

    def test_idle_needs_a_reconnect(self):
        owl = FakeOwl()
        out = self.checks(owl, idle=True)
        self.assertIn("ok - it went out on a new connection", out)
        self.assertIn("ok - pause goes through (pause: done)\n", out)
        self.assertEqual(owl.typed[-2:], ["play", "status"])
        owl = FakeOwl(reconnects=False)
        self.checks(owl, hil_spotify.Failure, idle=True)
        self.assertEqual(owl.status, "playing")

    def test_a_paused_start_is_left_paused(self):
        owl = FakeOwl(status="paused")
        out = self.checks(owl)
        self.assertEqual(owl.status, "paused")
        self.assertIn("put back: playback paused", out)


class RestoreTest(unittest.TestCase):
    checks = PlaybackTest.checks

    def test_a_failure_before_any_change_changes_nothing(self):
        owl = FakeOwl(fail={"pause"})
        out = self.checks(owl, hil_spotify.Failure)
        self.assertNotIn("left changed", out)
        self.assertEqual(owl.typed[-1], "status")

    def test_a_failed_volume_put_back_is_retried(self):
        owl = FakeOwl(fail_once={"vol 64"})
        out = self.checks(owl, hil_spotify.Failure)
        self.assertEqual(owl.volume, 64)
        self.assertIn("put back: volume 64", out)

    def test_a_volume_that_cannot_be_put_back_is_named(self):
        owl = FakeOwl(fail={"vol 64"})
        out = self.checks(owl, hil_spotify.Failure)
        self.assertIn("left changed: volume 54 (was 64)\n", out)

    def test_a_failed_transfer_back_is_retried(self):
        owl = FakeOwl(fail_once={"transfer dev1"})
        out = self.checks(owl, hil_spotify.Failure, transfer=True)
        self.assertEqual(owl.device, "dev1")
        self.assertIn("put back: playback on Desk", out)

    def test_a_track_the_test_liked_is_unliked_again(self):
        owl = FakeOwl(fail_once={"unlike"})
        out = self.checks(owl, hil_spotify.Failure)
        self.assertEqual(owl.library, set())
        self.assertIn(f"put back: {TRACKS[0]} out of Liked Songs", out)

    def test_a_track_that_started_liked_is_never_unliked(self):
        owl = FakeOwl(liked=True, fail_once={"vol 64"})
        self.checks(owl, hil_spotify.Failure)
        self.assertNotIn("unlike", owl.typed)
        self.assertEqual(owl.library, {TRACKS[0]})

    def test_ctrl_c_in_the_idle_wait_resumes_playback(self):
        owl = FakeOwl(interrupt=True)
        out = self.checks(owl, KeyboardInterrupt, idle=True)
        self.assertEqual(owl.status, "playing")
        self.assertIn("put back: playback playing", out)


class PrevTest(unittest.TestCase):
    checks = PlaybackTest.checks

    def test_prev_returns_to_the_first_track(self):
        owl = FakeOwl()
        out = self.checks(owl)
        self.assertEqual(owl.typed.count("prev"), 1)
        self.assertIn("ok - the first track plays again", out)

    def test_a_prev_that_restarts_the_skipped_track_is_sent_again(self):
        owl = FakeOwl(prev_restarts=1)
        with mock.patch.object(hil_spotify.Board, "wait_event", fast_wait_event):
            self.checks(owl)
        self.assertEqual(owl.typed.count("prev"), 2)
        self.assertEqual(owl.track, 0)

    def test_a_prev_that_never_goes_back_fails_and_names_both_tracks(self):
        owl = FakeOwl(prev_restarts=2)
        with mock.patch.object(hil_spotify.Board, "wait_event", fast_wait_event):
            out = self.checks(owl, hil_spotify.Failure)
        self.assertIn(f"left changed: track {TRACKS[1]} (was {TRACKS[0]})", out)
        self.assertEqual(self.error, f"prev did not go back from {TRACKS[1]} to {TRACKS[0]}")
        self.assertNotIn("unlike", owl.typed)


class MainTest(unittest.TestCase):
    def test_refuses_to_run_without_the_flag(self):
        err = io.StringIO()
        with mock.patch.object(sys, "argv", ["hil_spotify.py", "--transfer"]), redirect_stderr(err), \
                mock.patch.object(hil_spotify, "Board") as board:
            self.assertEqual(hil_spotify.main(), 2)
        board.assert_not_called()
        self.assertIn("--real-account", err.getvalue())

    def test_the_idle_wait_outlasts_the_fast_polling_and_the_server_keep_alive(self):
        self.assertGreater(hil_spotify.AWAKE_S, 0)
        self.assertGreater(hil_spotify.CONNECTION_IDLE_S, hil_spotify.SERVER_KEEP_ALIVE_S)


if __name__ == "__main__":
    unittest.main()
