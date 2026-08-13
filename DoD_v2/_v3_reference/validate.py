"""Sanity checks run on a freshly generated dashboard before it replaces the
previous known-good file."""
from __future__ import annotations

import json
import re
from pathlib import Path

MIN_SIZE_BYTES = 2_000_000  # plotly.js alone is ~4.8MB; a truncated file is a red flag
SECRET_PATTERNS = [r"sk-ant-[A-Za-z0-9\-_]{10,}", r"AKIA[0-9A-Z]{16}"]


def validate_dashboard_html(path: Path, expected_transaction_count: int | None = None) -> list[str]:
    """Returns a list of validation errors (empty list = passed)."""
    errors: list[str] = []
    if not path.exists():
        return [f"{path} does not exist"]

    size = path.stat().st_size
    if size < MIN_SIZE_BYTES:
        errors.append(f"File too small ({size} bytes < {MIN_SIZE_BYTES}) -- likely truncated or failed generation")

    text = path.read_text(errors="ignore")

    for marker in ["dashboard-data", "Executive Overview", "Transaction Explorer", "Plotly"]:
        if marker not in text:
            errors.append(f"Missing expected marker: {marker!r}")

    for pat in SECRET_PATTERNS:
        if re.search(pat, text):
            errors.append(f"Secret-shaped string found matching {pat!r}")

    m = re.search(r'<script id="dashboard-data" type="application/json">(.*?)</script>', text, re.S)
    if not m:
        errors.append("Could not locate embedded dashboard-data payload")
    else:
        try:
            payload = json.loads(m.group(1))
        except json.JSONDecodeError as exc:
            errors.append(f"Embedded payload is not valid JSON: {exc}")
        else:
            count = payload.get("meta", {}).get("transaction_count")
            if expected_transaction_count is not None and count != expected_transaction_count:
                errors.append(f"transaction_count mismatch: embedded={count} expected={expected_transaction_count}")

    return errors
