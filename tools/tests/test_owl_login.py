import json
import os
import pathlib
import queue
import socket
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import owl_login  # noqa: E402
from owl_login import normalize_client_id, read_callback, redirect_uri, serve_callback  # noqa: E402
from owl_serial import BoardError  # noqa: E402

try:
    import serial  # noqa: F401

    HAVE_SERIAL = True
except ImportError:
    HAVE_SERIAL = False

CLIENT = "0123456789abcdef0123456789abcdef"
STATE = "QEFCQ0RFRkdISUpLTE1OTw.192.168.1.23"


class CallbackTest(unittest.TestCase):
    def test_redirect_uri_is_a_loopback_address(self):
        self.assertEqual(redirect_uri(8765), "http://127.0.0.1:8765/callback")

    def test_client_ids_are_normalized_or_refused(self):
        self.assertEqual(normalize_client_id(" 0123456789ABCDEF0123456789abcdef \n"),
                         "0123456789abcdef0123456789abcdef")
        self.assertIsNone(normalize_client_id("0123456789abcdef"))
        self.assertIsNone(normalize_client_id("0123456789abcdef0123456789abcdeg"))

    def test_callback_parameters_are_read(self):
        self.assertEqual(read_callback("/callback?code=AQDx-y_z&state=QEFC.192.168.1.23"),
                         {"code": "AQDx-y_z", "state": "QEFC.192.168.1.23"})
        self.assertEqual(read_callback("/callback?error=access_denied&state=s"),
                         {"error": "access_denied", "state": "s"})
        self.assertEqual(read_callback("/favicon.ico"), {})
        self.assertEqual(read_callback("/callback/../x?code=1"), {})

    def test_server_hands_over_the_code_and_echoes_nothing(self):
        answers = queue.Queue()
        server = serve_callback(0, answers)
        port = server.server_address[1]
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/callback?code=SECRETCODE&state=s1") as page:
                body = page.read().decode()
            self.assertNotIn("SECRETCODE", body)
            self.assertEqual(answers.get(timeout=2), {"code": "SECRETCODE", "state": "s1"})
            with self.assertRaises(urllib.error.HTTPError) as missing:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/other?code=x")
            self.assertEqual(missing.exception.code, 404)
            self.assertTrue(answers.empty())
        finally:
            server.shutdown()
            server.server_close()


    def test_the_server_listens_on_the_loopback_address_only(self):
        server = serve_callback(0, queue.Queue())
        try:
            self.assertEqual(server.server_address[0], "127.0.0.1")
            self.assertEqual(server.RequestHandlerClass.timeout, 10)
        finally:
            server.shutdown()
            server.server_close()

    def test_an_idle_connection_does_not_hold_up_the_callback(self):
        answers = queue.Queue()
        server = serve_callback(0, answers)
        port = server.server_address[1]
        stray = socket.create_connection(("127.0.0.1", port))
        try:
            stray.sendall(b"GET /callback?code=")  # a request that never finishes
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/callback?code=AQD&state=s1", timeout=5) as page:
                page.read()
            self.assertEqual(answers.get(timeout=2), {"code": "AQD", "state": "s1"})
        finally:
            stray.close()
            server.shutdown()
            server.server_close()


class WaitAnswerTest(unittest.TestCase):
    def test_answers_for_another_login_are_skipped(self):
        answers = queue.Queue()
        answers.put({"code": "AQDold", "state": "an-earlier-login"})
        answers.put({"code": "AQDnew", "state": STATE})
        with mock.patch("builtins.print"):
            self.assertEqual(owl_login.wait_answer(answers, STATE, 1), {"code": "AQDnew", "state": STATE})

    def test_no_answer_in_time_is_a_failure(self):
        answers = queue.Queue()
        answers.put({"code": "AQDold", "state": "an-earlier-login"})
        with self.assertRaises(owl_login.Failure), mock.patch("builtins.print"):
            owl_login.wait_answer(answers, STATE, 0.3)


class TokenLeaksTest(unittest.TestCase):
    def test_a_normal_console_log_is_clean(self):
        log = ("I (1210) owltunes: OWL_BOOT_OK board=nano_esp32\n"
               '@owl {"id":3,"ok":true,"authorize_url":"https://accounts.spotify.com/authorize?client_id=<redacted>'
               "&response_type=code&redirect_uri=http%3A%2F%2F127.0.0.1%3A8765%2Fcallback"
               '&code_challenge_method=S256&code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"}\n'
               "I (9000) spotify_link: token endpoint answered 200 ok\n")
        self.assertEqual(owl_login.token_leaks(log), [])

    def test_token_field_names_are_found(self):
        self.assertEqual(len(owl_login.token_leaks('x\n{"access_token":"BQD"}\nrefresh_token=AQ\n')), 2)

    def test_long_base64url_runs_are_found_without_repeating_them(self):
        token = "AQ" + "x_-9" * 20  # 82 characters
        reasons = owl_login.token_leaks(f"I (1) x: {token}\n")
        self.assertEqual(len(reasons), 1)
        self.assertIn("line 1", reasons[0])
        self.assertNotIn(token, reasons[0])
        self.assertEqual(owl_login.token_leaks("A" * 79), [])


class ClientIdTest(unittest.TestCase):
    def client_id(self, flag, env_file, environ):
        args = mock.Mock(client_id=flag)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(owl_login, "ROOT", pathlib.Path(d)), \
                mock.patch.dict(owl_login.os.environ, environ, clear=True):
            if env_file is not None:
                pathlib.Path(d, "private").mkdir()
                pathlib.Path(d, "private", "hil.env").write_text(env_file)
            return owl_login.client_id_from(args)

    def test_the_flag_then_the_environment_then_the_private_file(self):
        other = "f" * 32
        self.assertEqual(self.client_id(None, f"OWL_SPOTIFY_CLIENT_ID={CLIENT.upper()}\n", {}), CLIENT)
        self.assertEqual(self.client_id(None, f"OWL_SPOTIFY_CLIENT_ID={CLIENT}\n",
                                        {"OWL_SPOTIFY_CLIENT_ID": other}), other)
        self.assertEqual(self.client_id(other, f"OWL_SPOTIFY_CLIENT_ID={CLIENT}\n", {}), other)

    def test_a_missing_or_malformed_client_id_is_a_failure(self):
        for env_file in (None, "OWL_SPOTIFY_CLIENT_ID=0123\n"):
            with self.subTest(env_file=env_file), self.assertRaises(owl_login.Failure):
                self.client_id(None, env_file, {})


class OnlineBoard:
    """Answers hello like a board that joins its network after a few tries."""

    def __init__(self, offline_hellos, networks=("Home",)):
        self.offline_hellos = offline_hellos
        self.networks = list(networks)
        self.hellos = 0

    def hello(self):
        self.hellos += 1
        ip = "" if self.hellos <= self.offline_hellos else "192.168.1.23"
        return {"name": "OwlTunes-7DF8", "ip": ip, "networks": self.networks}


class WaitOnlineTest(unittest.TestCase):
    def wait(self, board, timeout=60):
        clock = iter(range(0, 1000, 2))
        with mock.patch.object(owl_login.time, "monotonic", side_effect=lambda: float(next(clock))), \
                mock.patch.object(owl_login.time, "sleep"):
            return owl_login.wait_online(board, timeout)

    def test_the_owl_is_asked_until_it_has_an_address(self):
        board = OnlineBoard(offline_hellos=3)
        self.assertEqual(self.wait(board)["ip"], "192.168.1.23")
        self.assertEqual(board.hellos, 4)

    def test_an_owl_that_stays_offline_is_a_failure(self):
        with self.assertRaises(owl_login.Failure):
            self.wait(OnlineBoard(offline_hellos=1000), timeout=20)

    def test_an_owl_without_a_saved_network_fails_at_once(self):
        board = OnlineBoard(offline_hellos=1000, networks=())
        with self.assertRaises(owl_login.Failure):
            self.wait(board)
        self.assertEqual(board.hellos, 1)


class RebootingBoard:
    """A board for boot_check: each reset gives the next scripted outcome of the boot check."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.resets = 0

    def reset(self):
        self.resets += 1
        return 0

    def wait_boot(self, timeout=20.0, since=0):
        return 0

    def hello(self):
        return {"ok": True}

    def wait_event(self, event, state=None, timeout=30.0, since=0, where=None):
        outcome = self.outcomes.pop(0)
        if outcome is None:
            raise BoardError("timed out")
        msg = {"event": event, **outcome}
        assert where is None or where(msg)
        return msg


class BootCheckTest(unittest.TestCase):
    def check(self, outcomes):
        board = RebootingBoard(outcomes)
        with mock.patch("builtins.print"):
            owl_login.boot_check(board)
        return board.resets

    def test_a_saved_login_that_passes(self):
        self.assertEqual(self.check([{"state": "linked"}]), 1)

    def test_a_missed_check_resets_once_more(self):
        self.assertEqual(self.check([None, {"state": "linked"}]), 2)

    def test_two_missed_checks_fail(self):
        with self.assertRaises(owl_login.Failure):
            self.check([None, None])

    def test_a_refused_login_fails(self):
        for outcome in ({"state": "logged_out", "error": "invalid_grant"}, {"state": "failed", "error": "storage"}):
            with self.subTest(outcome=outcome), self.assertRaises(owl_login.Failure) as refused:
                self.check([outcome])
            self.assertIn(f"({outcome['state']} {outcome['error']})", str(refused.exception))

    def test_the_passing_check_is_reported_plainly(self):
        with mock.patch("builtins.print") as printed:
            owl_login.boot_check(RebootingBoard([{"state": "linked"}]))
        self.assertIn("passes its check with Spotify (linked)", printed.call_args.args[0])


class LoginOwl:
    """A pseudo-terminal that answers the login requests like the firmware does."""

    def __init__(self, exchange="linked"):
        self.master, self.slave = os.openpty()
        self.port = os.ttyname(self.slave)
        self.exchange = exchange
        self.client_id = ""
        self.redirect_uri = ""
        self.state = ""
        self.codes = []
        self.linked = False
        threading.Thread(target=self.run, daemon=True).start()

    def send(self, msg):
        os.write(self.master, ("@owl " + json.dumps(msg, separators=(",", ":")) + "\r\n").encode())

    def run(self):
        pending = b""
        while True:
            try:
                pending += os.read(self.master, 1024)
            except OSError:
                return
            while b"\n" in pending:
                raw, pending = pending.split(b"\n", 1)
                line = raw.decode()
                if line.startswith("@owl "):
                    self.answer(json.loads(line[5:]))

    def answer(self, req):
        rid, cmd = req["id"], req["cmd"]
        if cmd == "hello":
            self.send({"id": rid, "ok": True, "name": "OwlTunes-7DF8", "ip": "192.168.1.23", "networks": ["Home"],
                       "linked": self.linked, "setup": "ready" if self.linked else "needs_spotify",
                       "client_id": self.client_id, "redirect_uri": self.redirect_uri})
        elif cmd == "spotify_client":
            self.client_id, self.redirect_uri = req["client_id"], req["redirect_uri"]
            self.send({"id": rid, "ok": True})
        elif cmd == "spotify_begin":
            self.state = STATE
            query = urllib.parse.urlencode({"client_id": self.client_id, "response_type": "code",
                                            "redirect_uri": self.redirect_uri, "state": self.state})
            self.send({"id": rid, "ok": True, "authorize_url": f"https://accounts.spotify.com/authorize?{query}"})
        elif cmd == "spotify_code":
            if req.get("state") != self.state:
                self.send({"id": rid, "ok": False, "error": "bad_state"})
                return
            self.codes.append(req["code"])
            self.send({"id": rid, "ok": True, "accepted": True})
            self.send({"event": "spotify", "state": "linking"})
            self.linked = self.exchange == "linked"
            self.send({"event": "spotify", "state": "linked"} if self.linked else
                      {"event": "spotify", "state": "failed", "error": "invalid_grant"})

    def close(self):
        os.close(self.master)
        os.close(self.slave)


@unittest.skipUnless(HAVE_SERIAL, "pyserial is not installed")
class LinkTest(unittest.TestCase):
    """link() against a fake owl, with a stand-in browser that Spotify sends back to the callback."""

    def setUp(self):
        self.owl = None
        self.board = None
        self.visits = []

    def tearDown(self):
        if self.board is not None:
            self.board.close()
        if self.owl is not None:
            self.owl.close()

    def browser(self, *queries):
        """Each query is what Spotify adds to the redirect URI; the state is filled in when missing."""

        def visit(url):
            params = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
            for query in queries:
                back = f"{params['redirect_uri']}?{urllib.parse.urlencode({'state': params['state'], **query})}"
                self.visits.append(back)
                try:
                    urllib.request.urlopen(back, timeout=5).read()
                except urllib.error.HTTPError:
                    pass

        return lambda url: threading.Thread(target=visit, args=(url,), daemon=True).start()

    def link(self, exchange="linked", queries=({"code": "AQDtest-code"},)):
        from owl_serial import Board

        self.owl = LoginOwl(exchange)
        self.board = Board(self.owl.port)
        with mock.patch.object(owl_login.webbrowser, "open", side_effect=self.browser(*queries)), \
                mock.patch("builtins.print"):
            owl_login.link(self.board, CLIENT, 0, True)

    def test_the_code_reaches_the_owl_and_the_login_is_saved(self):
        self.link()
        self.assertEqual(self.owl.codes, ["AQDtest-code"])
        self.assertEqual(self.owl.client_id, CLIENT)
        self.assertRegex(self.owl.redirect_uri, r"^http://127\.0\.0\.1:\d+/callback$")
        self.assertTrue(self.visits[0].startswith(self.owl.redirect_uri + "?"))
        self.assertTrue(self.owl.linked)

    def test_a_callback_for_another_login_is_skipped(self):
        self.link(queries=({"code": "AQDstale", "state": "an-earlier-login"}, {"code": "AQDtest-code"}))
        self.assertEqual(self.owl.codes, ["AQDtest-code"])

    def test_a_refused_login_is_a_failure(self):
        with self.assertRaises(owl_login.Failure) as refused:
            self.link(queries=({"error": "access_denied"},))
        self.assertIn("access_denied", str(refused.exception))
        self.assertEqual(self.owl.codes, [])

    def test_a_failed_exchange_is_a_failure(self):
        with self.assertRaises(owl_login.Failure) as failed:
            self.link(exchange="failed")
        self.assertIn("invalid_grant", str(failed.exception))

    def test_no_answer_from_spotify_is_a_failure(self):
        with mock.patch.object(owl_login, "LOGIN_TIMEOUT_S", 0.5), self.assertRaises(owl_login.Failure):
            self.link(queries=())


if __name__ == "__main__":
    unittest.main()
