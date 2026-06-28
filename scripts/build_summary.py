#!/usr/bin/env python3
"""Fetch peer-comparison metrics and render the summary canvas in one step."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
FETCH = SCRIPTS / "fetch_summary.py"
RENDER = SCRIPTS / "render_summary_canvas.py"
SUMMARY_DATA = ROOT / "summary-data"
CANVAS_DIR = ROOT / "canvas"


def slugify(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return s.strip("-") or "stock-summary"


def main() -> None:
    p = argparse.ArgumentParser(description="Build a stock summary canvas from Yahoo Finance")
    p.add_argument("symbols", nargs="+", help="Ticker symbols")
    p.add_argument("--title", required=True, help="Title shown in the table header")
    p.add_argument("--slug", help="Output basename (default: slugified --title)")
    p.add_argument(
        "--allow-gaps",
        action="store_true",
        help="Render even when some symbols lack fundamentals (gaps reported on stderr)",
    )
    args = p.parse_args()

    slug = args.slug or slugify(args.title)
    SUMMARY_DATA.mkdir(parents=True, exist_ok=True)
    CANVAS_DIR.mkdir(parents=True, exist_ok=True)

    json_path = SUMMARY_DATA / f"{slug}.json"
    canvas_path = CANVAS_DIR / f"{slug}.canvas.tsx"

    fetch = subprocess.run(
        [sys.executable, str(FETCH), *args.symbols, "-o", str(json_path)],
        capture_output=True,
        text=True,
    )
    if fetch.stderr:
        print(fetch.stderr, file=sys.stderr, end="")
    if fetch.returncode not in (0, 2):
        if fetch.stdout:
            print(fetch.stdout, file=sys.stderr)
        sys.exit(fetch.returncode or 1)

    data = json.loads(json_path.read_text())
    gaps = data.get("gaps") or {}
    if gaps and not args.allow_gaps:
        print(
            json.dumps({"error": "missing fields", "gaps": gaps, "json": str(json_path)}, indent=2),
            file=sys.stderr,
        )
        sys.exit(2)

    render = subprocess.run(
        [
            sys.executable,
            str(RENDER),
            str(json_path),
            "-o",
            str(canvas_path),
            "--title",
            args.title,
        ],
    )
    if render.returncode != 0:
        sys.exit(render.returncode)

    print(
        json.dumps(
            {
                "slug": slug,
                "title": args.title,
                "symbols": data["symbols"],
                "asOf": data.get("asOf"),
                "json": str(json_path),
                "canvas": str(canvas_path),
                "gaps": gaps,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
