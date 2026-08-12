"""Renders the self-contained NASA Procurement Intelligence Dashboard HTML.

Everything the browser needs -- Plotly.js, CSS, JS app logic, and the
processed data payload -- is inlined into one HTML file. No CDN, no
external file references, no network calls at view time.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

import plotly
from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).resolve().parent
PLOTLY_JS_PATH = Path(plotly.__file__).resolve().parent / "package_data" / "plotly.min.js"


def _json_safe(obj):
    """Recursively replace NaN/Infinity floats with None so the payload is
    strict, browser-parseable JSON (Python's json.dumps otherwise emits the
    non-standard NaN/Infinity literals)."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    return obj


def _no_secrets_check(text: str) -> None:
    """Defense-in-depth: fail loudly if anything resembling a secret made it
    into the generated HTML (belt-and-suspenders on top of never embedding
    ANTHROPIC_API_KEY in the payload in the first place)."""
    import re

    patterns = [r"sk-ant-[A-Za-z0-9\-_]{10,}", r"AKIA[0-9A-Z]{16}"]
    for pat in patterns:
        if re.search(pat, text):
            raise RuntimeError(f"Secret-shaped string matched pattern {pat!r} in generated dashboard HTML -- refusing to write file.")


def render_dashboard(payload: dict, out_path: Path) -> Path:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("template.html.j2")

    plotly_js = PLOTLY_JS_PATH.read_text()
    app_js = (TEMPLATE_DIR / "app.js").read_text()
    payload_json = json.dumps(_json_safe(payload), default=str, allow_nan=False)

    html = template.render(
        payload_json=payload_json,
        plotly_js=plotly_js,
        app_js=app_js,
        generated_at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )

    _no_secrets_check(html)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(".tmp.html")
    tmp_path.write_text(html)
    tmp_path.replace(out_path)
    return out_path
