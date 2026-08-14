"""Produces a hostable, size-trimmed copy of the full FY2020-2026 dashboard.

The complete build is ~19.7 MB, over the 16 MB Artifact limit and heavy for
a web page. Rather than re-running the pipeline with a smaller row cap, this
lifts the already-computed payload out of the built HTML, trims only the
Transaction Explorer's embedded row cache -- a display convenience whose cap
the tab already discloses, not an analytical result -- and re-renders.

Every analytical section (standouts by range, the bid-competition review,
supplier and category detail) is carried over untouched, so the trimmed file
and the full one agree on every number.

Usage:  python3 tools/make_web_build.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "/home/user/Repository-Anderson-AI/v4/nasa_procurement")
from src.dashboard.generate import render_dashboard  # noqa: E402

BASE = Path("/home/user/Repository-Anderson-AI/v4/nasa_procurement/outputs")
SRC = BASE / "nasa_fy2019_present_realdata_dashboard.html"
OUT = BASE / "nasa_procurement_dashboard_web.html"
ROW_LIMIT = 1500

html = SRC.read_text(encoding="utf-8")
payload = json.loads(
    re.search(r'<script id="dashboard-data" type="application/json">(.*?)</script>', html, re.S).group(1)
)

before = len(payload["explorer_rows"])
payload["explorer_rows"] = payload["explorer_rows"][:ROW_LIMIT]
payload["meta"]["explorer_embedded_count"] = len(payload["explorer_rows"])
payload["meta"]["explorer_row_limit"] = ROW_LIMIT
print(f"explorer rows {before:,} -> {len(payload['explorer_rows']):,}")

render_dashboard(payload, OUT)
size = OUT.stat().st_size
print(f"wrote {OUT} ({size/1e6:.1f} MB) {'OK under 16MB' if size < 16e6 else 'STILL TOO BIG'}")
