#!/usr/bin/env python3
"""Query JLCPCB for stock and library type of every LCSC number in a board's design.toml.

Prints one line per unique part: LCSC, MPN, Basic or Extended, stock, quantity needed and OK or
LOW. Prices are written only to the --prices CSV, which must be under the main checkout's private/ folder. Needs network.

Usage: python3 tools/hw/hw_stock.py owl-mainboard --boards 5 --prices private/hw-rev-a/prices-main.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
import urllib.request
from collections import Counter
from pathlib import Path

from hw_netlist import ROOT, load_design


def private_root() -> Path:
    """The main checkout's private/ folder, shared by all worktrees (never inside the worktree)."""
    out = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=ROOT,
                         check=True, capture_output=True, text=True).stdout.strip()
    return Path(out).parent / "private"


URL = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"


def query(lcsc: str) -> dict | None:
    body = json.dumps({"keyword": lcsc, "currentPage": 1, "pageSize": 5}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        rows = (json.load(r).get("data") or {}).get("componentPageInfo", {}).get("list") or []
    return next((c for c in rows if c.get("componentCode") == lcsc), None)


def needed(per_board: int, boards: int) -> int:
    """Quantity to order: 10 percent attrition, at least 2 spare."""
    return max(per_board * boards + 2, math.ceil(per_board * boards * 1.1))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--boards", type=int, default=5)
    ap.add_argument("--prices", type=Path)
    args = ap.parse_args(argv)
    parts = [p for p in load_design(args.board)["part"] if p.get("assembled", True)]
    counts = Counter(p["lcsc"] for p in parts)
    mpn = {p["lcsc"]: p.get("mpn", "") for p in parts}
    low = 0
    rows = []
    for lcsc, n in sorted(counts.items()):
        c = query(lcsc)
        need = needed(n, args.boards)
        if c is None:
            print(f"{lcsc:>10} {mpn[lcsc]:28} NOT FOUND")
            low += 1
            continue
        kind = "Basic" if c["componentLibraryType"] == "base" else "Extended"
        ok = c["stockCount"] >= need
        low += 0 if ok else 1
        print(f"{lcsc:>10} {mpn[lcsc]:28} {kind:8} stock {c['stockCount']:>8} need {need:>5} {'OK' if ok else 'LOW'}")
        price = (c.get("componentPrices") or [{}])[0].get("productPrice")
        rows.append([lcsc, mpn[lcsc], kind, c["stockCount"], need, price])
    if args.prices:
        try:
            args.prices.resolve().relative_to(private_root().resolve())
        except ValueError:
            print(f"refusing to write prices outside {private_root()}")
            return 2
        args.prices.parent.mkdir(parents=True, exist_ok=True)
        with args.prices.open("w", newline="") as f:
            csv.writer(f).writerows([["lcsc", "mpn", "type", "stock", "need", "unit_usd"], *rows])
    print(f"{args.board}: {len(counts)} unique parts, {low} low or missing")
    return 1 if low else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
