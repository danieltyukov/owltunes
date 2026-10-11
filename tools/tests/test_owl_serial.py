import json
import os
import pathlib
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from owl_serial import Board, BoardError, find_port, load_env_file, parse_line, redact_line  # noqa: E402

try:
    import serial  # noqa: F401

    HAVE_SERIAL = True
except ImportError:
    HAVE_SERIAL = False


class ParseLineTest(unittest.TestCase):
    def test_protocol_lines_become_objects(self):
        self.assertEqual(parse_line('@owl {"event":"network","state":"up"}'), {"event": "network", "state": "up"})

    def test_log_lines_and_junk_are_ignored(self):
        self.assertIsNone(parse_line("I (412) owltunes: OWL_BOOT_OK board=nano_esp32"))
        self.assertIsNone(parse_line("@owl {not json"))
        self.assertIsNone(parse_line('@owl ["a list"]'))
        self.assertIsNone(parse_line('@owl{"event":"x"}'))


class FindPortTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.pattern = os.path.join(self.dir.name, "*Espressif*")

    def tearDown(self):
        self.dir.cleanup()

    def touch(self, name):
        pathlib.Path(self.dir.name, name).touch()

    def test_explicit_port_wins(self):
        self.assertEqual(find_port("/dev/ttyACM3", self.pattern), "/dev/ttyACM3")

    def test_one_board_is_found(self):
        self.touch("usb-Espressif_USB_JTAG_serial_debug_unit_34:85:18:7B:7D:F8-if00")
        self.assertTrue(find_port(None, self.pattern).endswith("7D:F8-if00"))

    def test_no_board_or_two_boards_is_an_error(self):
        with self.assertRaises(BoardError):
            find_port(None, self.pattern)
        self.touch("usb-Espressif_one-if00")
        self.touch("usb-Espressif_two-if00")
        with self.assertRaises(BoardError):
            find_port(None, self.pattern)


class LoadEnvFileTest(unittest.TestCase):
    def test_keys_values_and_comments(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d, "hil.env")
            path.write_text("# private\nOWL_WIFI_SSID = Home 5G\n\nOWL_WIFI_PASSWORD=a=b#c\nnot a setting\n")
            self.assertEqual(load_env_file(path), {"OWL_WIFI_SSID": "Home 5G", "OWL_WIFI_PASSWORD": "a=b#c"})

    def test_missing_file_is_empty(self):
        self.assertEqual(load_env_file(pathlib.Path("/nonexistent/hil.env")), {})


class FakeOwl:
    """A pseudo-terminal that answers like the firmware: log noise, split writes, @owl replies."""

    def __init__(self):
        self.master, slave = os.openpty()
        self.port = os.ttyname(slave)
        self.slave = slave
        self.received = []
        threading.Thread(target=self.run, daemon=True).start()

    def send(self, text):
        os.write(self.master, text.encode())

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
                self.received.append(line)
                self.answer(line)

    def answer(self, line):
        if line.startswith("@owl "):
            req = json.loads(line[5:])
            if len(self.received) == 1:
                return  # still booting: the first hello goes unanswered
            reply = json.dumps({"id": req["id"], "ok": True, "name": "OwlTunes-7DF8", "protocol": 1})
            self.send("I (1200) wifi: joining\r\n@owl " + reply[:20])
            self.send(reply[20:] + "\r\n")
        elif line == "info":
            self.send('@owl {"event":"time","state":"synced"}\r\n@owl {"event":"info","board":"nano_esp32"}\r\n')

    def close(self):
        os.close(self.master)
        os.close(self.slave)


@unittest.skipUnless(HAVE_SERIAL, "pyserial is not installed")
class BoardTest(unittest.TestCase):
    def setUp(self):
        self.owl = FakeOwl()
        self.board = Board(self.owl.port)

    def tearDown(self):
        self.board.close()
        self.owl.close()

    def test_hello_is_retried_until_the_board_answers(self):
        hello = self.board.hello(timeout=10)
        self.assertEqual(hello["name"], "OwlTunes-7DF8")
        self.assertGreaterEqual(len(self.owl.received), 2)

    def test_commands_wait_for_their_own_event(self):
        info = self.board.command("info", "info")
        self.assertEqual(info["board"], "nano_esp32")
        self.assertIn("info", self.owl.received)

    def test_events_already_received_are_found(self):
        since = self.board.type("info")
        self.board.wait_event("info", since=since)
        self.assertEqual(self.board.wait_event("time", "synced", since=since, timeout=0.1)["state"], "synced")

    def test_the_boot_line_is_waited_for_and_found_later_too(self):
        self.owl.send("I (412) owltunes: OWL_BOOT_OK board=nano_esp32\r\n")
        self.board.wait_boot(timeout=5)
        self.assertEqual(self.board.wait_boot(timeout=0.1), len(self.board.lines))

    def test_a_missing_boot_line_times_out(self):
        with self.assertRaises(BoardError):
            self.board.wait_boot(timeout=0.3)

    def test_a_missing_answer_times_out(self):
        with self.assertRaises(BoardError):
            self.board.wait_event("never", timeout=0.3)


class RedactLineTest(unittest.TestCase):
    def test_client_ids_are_hidden_wherever_the_owl_prints_them(self):
        hello = '@owl {"id":1,"ok":true,"client_id":"0123456789ABCDEF0123456789abcdef","redirect_uri":"x"}'
        self.assertEqual(redact_line(hello), '@owl {"id":1,"ok":true,"client_id":"<redacted>","redirect_uri":"x"}')
        url = "https://accounts.spotify.com/authorize?client_id=fedcba9876543210fedcba9876543210&response_type=code"
        self.assertEqual(redact_line(url), "https://accounts.spotify.com/authorize?client_id=<redacted>&response_type=code")

    def test_other_text_is_left_alone(self):
        for line in ('@owl {"id":1,"ok":true,"client_id":"","linked":false}', "I (412) owltunes: OWL_BOOT_OK",
                     '"client_id":"0123456789abcdef0123456789abcdef0"', "client_id=0123"):
            with self.subTest(line=line):
                self.assertEqual(redact_line(line), line)

    def test_extra_text_is_hidden_too(self):
        self.assertEqual(redact_line("saved for Home", ("Home", "")), "saved for <redacted>")


@unittest.skipUnless(HAVE_SERIAL, "pyserial is not installed")
class RedactTest(unittest.TestCase):
    def open_board(self, **kwargs):
        owl = FakeOwl()
        self.addCleanup(owl.close)
        log = pathlib.Path(self.enterContext(tempfile.TemporaryDirectory()), "console.log")
        board = Board(owl.port, log, **kwargs)
        self.addCleanup(board.close)
        self.addCleanup(board._log.close)  # Board keeps its log open across reopen() and close()
        return owl, board, log

    def test_a_client_id_never_passed_in_is_hidden_in_the_log(self):
        client = "89abcdef0123456789abcdef01234567"  # what an already linked board holds
        owl, board, log = self.open_board()
        owl.send('I (1) boot\r\n@owl {"id":1,"ok":true,"client_id":"' + client + '"}\r\n')
        self.assertEqual(board.wait(lambda line: line if client in line else None, 5, "the hello"),
                         '@owl {"id":1,"ok":true,"client_id":"' + client + '"}')
        text = log.read_text()
        self.assertNotIn(client, text)
        self.assertIn('"client_id":"<redacted>"', text)
        self.assertIn("I (1) boot\n", text)

    def test_the_log_file_hides_redacted_text_but_the_lines_keep_it(self):
        client = "0123456789abcdef0123456789abcdef"
        owl, board, log = self.open_board(redact=(client, ""))
        owl.send("I (2) saved " + client + "\r\n")
        board.wait(lambda line: line if client in line else None, 5, "the line")
        text = log.read_text()
        self.assertNotIn(client, text)
        self.assertIn("I (2) saved <redacted>\n", text)


if __name__ == "__main__":
    unittest.main()
