import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "hw"))
import hw_stock  # noqa: E402


class StockTest(unittest.TestCase):
    def test_needed_adds_attrition_with_two_spares_minimum(self):
        self.assertEqual(hw_stock.needed(1, 5), 7)
        self.assertEqual(hw_stock.needed(2, 5), 12)
        self.assertEqual(hw_stock.needed(20, 5), 110)

    def test_prices_outside_private_are_refused_before_any_query(self):
        with mock.patch.object(hw_stock, "private_root", return_value=pathlib.Path("/nonexistent/private")):
            with self.assertRaises(ValueError):
                hw_stock.resolve_prices(pathlib.Path("/tmp/prices.csv"))
            self.assertIsNone(hw_stock.resolve_prices(None))
            ok = hw_stock.resolve_prices(pathlib.Path("/nonexistent/private/hw-rev-a/p.csv"))
            self.assertEqual(ok, pathlib.Path("/nonexistent/private/hw-rev-a/p.csv"))

    def test_main_refuses_a_bad_prices_path_without_querying(self):
        with mock.patch.object(hw_stock, "query") as q, \
                mock.patch.object(hw_stock, "private_root", return_value=pathlib.Path("/nonexistent/private")), \
                mock.patch("builtins.print"):
            self.assertEqual(hw_stock.main(["owl-mainboard", "--prices", "/tmp/p.csv"]), 2)
            q.assert_not_called()

    def test_network_error_and_missing_keys_are_reported_not_raised(self):
        design = {"part": [{"ref": "R1", "lcsc": "C1", "mpn": "A"}, {"ref": "R2", "lcsc": "C2", "mpn": "B"},
                           {"ref": "R3", "lcsc": "C3", "mpn": "C"}]}
        answers = {"C1": OSError("offline"), "C2": {"componentCode": "C2"},
                   "C3": {"componentLibraryType": "base", "stockCount": 1000}}

        def fake(lcsc):
            a = answers[lcsc]
            if isinstance(a, Exception):
                raise a
            return a

        with mock.patch.object(hw_stock, "load_design", return_value=design), mock.patch.object(hw_stock, "query", fake):
            with mock.patch("builtins.print") as pr:
                code = hw_stock.main(["x"])
        out = "\n".join(str(c.args[0]) for c in pr.call_args_list)
        self.assertEqual(code, 1)
        self.assertIn("QUERY FAILED: offline", out)
        self.assertIn("UNEXPECTED ANSWER", out)
        self.assertIn("x: 3 unique parts, 2 low or missing", out)


if __name__ == "__main__":
    unittest.main()
