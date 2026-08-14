"""Paths, constants, and environment loading for the NASA procurement pipeline."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache"
SAMPLES_DIR = DATA_DIR / "samples"
OUTPUTS_DIR = ROOT / "outputs"
CONFIG_DIR = ROOT / "config"

for d in (RAW_DIR, PROCESSED_DIR, CACHE_DIR, SAMPLES_DIR, OUTPUTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# --- USAspending scope ---------------------------------------------------
NASA_AGENCY_NAME = "National Aeronautics and Space Administration"
NASA_TOPTIER_CODE = "080"
FY2020_START = "2019-10-01"  # federal FY2020 begins 2019-10-01

# Prime contract award-type codes only (definitive/delivery order contracts,
# purchase orders, BPA calls). Excludes IDVs (parent vehicles, not
# transactions themselves), assistance codes, and loans.
CONTRACT_AWARD_TYPE_CODES = ["A", "B", "C", "D"]

# Award type codes that indicate financial assistance (grants, loans, direct
# payments, other assistance) or subawards -- used only for post-ingestion
# validation that none leaked into the dataset.
ASSISTANCE_AWARD_TYPE_CODES = {
    "02", "03", "04", "05", "06", "07", "08", "09", "10", "11",
}

USASPENDING_BASE_URL = "https://api.usaspending.gov"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5").strip()

DASHBOARD_PATH = OUTPUTS_DIR / "nasa_procurement_dashboard.html"

# Row cap for records embedded directly in the Transaction Explorer table.
# The full processed dataset always lives in data/processed/ regardless of
# this limit -- this only bounds what ships inside the HTML file itself.
EXPLORER_EMBED_ROW_LIMIT = int(os.environ.get("EXPLORER_EMBED_ROW_LIMIT", "8000"))

TAXONOMY_VERSION_PATH = CONFIG_DIR / "taxonomy.json"

# Product/Service Codes the Misuse Protection screen sets aside by default
# (proprietary software licensing, where a single offer is the expected
# outcome rather than a competition-avoidance signal). Editable without a
# code change; see the file's own "_comment" for the inclusion rationale.
MISUSE_EXCLUDED_PSC_PATH = CONFIG_DIR / "misuse_excluded_psc.json"
