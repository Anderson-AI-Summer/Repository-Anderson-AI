# -*- coding: utf-8 -*-
"""
DoD procurement analytics pipeline, adapted from v3/nasa_procurement's
src/analytics.py + src/dashboard/data_prep.py logic, applied to DoD_v1's
existing award-level bulk data (95,895 definitive contracts, FY2020-FY2026 YTD).

DISCLOSED SCOPE DIFFERENCE FROM v3: v3 operates on true per-transaction
signed obligation data (each contract modification as its own signed row,
enabling deobligation/reversal-pair detection). DoD_v1's bulk pull is
award-level (one row per contract award, its current total obligated value
as of extraction) -- there is no per-modification transaction history in
this dataset. Consequently: every amount here is treated as a positive
"transaction" (no deobligation/negative-transaction analysis is possible),
and "transaction count" == "award count" (1:1), unlike v3 where one award
can have many transactions. This is disclosed throughout the dashboard
rather than silently presented as equivalent to v3's granularity.
"""
import json, glob, re
from collections import defaultdict
import pandas as pd
import numpy as np

DATA_DIR = r"C:\finances\DoD_v1\sba_loans\offers_fullrange"
TAXONOMY_PATH = r"C:\finances\DoD_v2\config\dod_taxonomy.json"
OUT_DIR = r"C:\finances\DoD_v2\data"

import os
os.makedirs(OUT_DIR, exist_ok=True)

# ============================================================
# 1. LOAD
# ============================================================
print("Loading CSVs...")
files = glob.glob(f"{DATA_DIR}/*.csv")
dfs = [pd.read_csv(f, encoding="utf-8-sig", low_memory=False) for f in files]
df = pd.concat(dfs, ignore_index=True)
print(f"Loaded {len(df):,} rows from {len(files)} files")

# ============================================================
# 2. CLEAN / DERIVE CORE FIELDS
# ============================================================
def pick_amount(row):
    for c in ("total_dollars_obligated", "current_total_value_of_award", "potential_total_value_of_award"):
        if c in df.columns:
            v = row.get(c)
            if pd.notna(v) and v != 0:
                return float(v)
    return 0.0

df["amount"] = df.apply(pick_amount, axis=1)
df["action_date"] = pd.to_datetime(df["award_latest_action_date"], errors="coerce")
df = df[df["action_date"].notna()].copy()
df["fiscal_year"] = df["action_date"].apply(lambda d: d.year + 1 if d.month >= 10 else d.year)
# Scope to the intended FY2020-FY2026 window (a handful of rows show a
# latest_action_date outside it -- API overlap artifact noted earlier).
df = df[(df["fiscal_year"] >= 2020) & (df["fiscal_year"] <= 2026)].copy()

def clean_description(raw):
    if pd.isna(raw):
        return ""
    s = str(raw)
    if s.count("!") > 5:
        return ""  # legacy pipe-delimited raw dump, not usable text
    s = re.sub(r"^IGF::OT::IGF\s*", "", s).strip()
    return s

df["transaction_description"] = df["prime_award_base_transaction_description"].apply(clean_description)
df["recipient_name_raw"] = df["recipient_name"].fillna("UNKNOWN")
df["award_id_piid"] = df["award_id_piid"].fillna("UNKNOWN")
df["transaction_id"] = df["award_id_piid"]  # 1 award = 1 "transaction" in this dataset (see module docstring)

# --- Data-quality: implausible single-award values ---
# Two records show current_total_value_of_award figures that are 2-3+
# orders of magnitude larger than every comparable peer award, with no
# plausible public-record explanation (unlike e.g. the Olmsted Dam award,
# $12.3B, kept -- a genuinely famous, well-documented USACE megaproject):
#   - W912UM09C0007 (SK Ecoplant, Korea/Camp Humphreys construction): ~$590B,
#     vs. the single largest legitimate award in this dataset at $109.4B.
#   - W912UM13C0025 (Seohee Construction, Korea/Osan AB "hospital
#     addition/alteration"): ~$27.0B, vs. the other 269 Korea-district
#     (W912UM*/Far East District) awards in this dataset totaling just
#     ~$2.4B combined -- this one row is larger than all its peers combined
#     by 3 orders of magnitude.
# Consistent with this session's earlier finding of a corrupted $6.58B FSRS
# subaward record, both are treated as source-data errors (plausibly a
# currency/unit mismatch on Korea-based awards), not real spend -- flagged
# and excluded from analysis rather than silently deleted.
IMPLAUSIBLE_AWARD_IDS = {"W912UM09C0007", "W912UM13C0025"}
implausible_mask = df["award_id_piid"].isin(IMPLAUSIBLE_AWARD_IDS)
n_implausible = int(implausible_mask.sum())
implausible_awards = df.loc[implausible_mask, ["award_id_piid", "recipient_name_raw", "amount"]].to_dict("records")
if n_implausible:
    print(f"Excluding {n_implausible} data-quality anomaly row(s): {implausible_awards}")
df = df[~implausible_mask].copy()

print(f"After date/FY filtering: {len(df):,} rows")
print(f"Total amount: ${df['amount'].sum():,.0f}")

# ============================================================
# 3. SUPPLIER RESOLUTION (UEI-primary, mirrors v3's supplier_resolution.py)
# ============================================================
SUFFIXES = {
    "INCORPORATED", "INC", "CORPORATION", "CORP", "COMPANY", "CO",
    "LLC", "LLP", "LP", "LTD", "LIMITED", "PLLC", "PC", "PA",
    "GROUP", "HOLDINGS", "ENTERPRISES",
}
_PUNCT_RE = re.compile(r"[.,\-&/\\()]")
_WS_RE = re.compile(r"\s+")

def normalize_name(raw):
    s = str(raw).upper()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    tokens = s.split(" ")
    while tokens and tokens[-1] in SUFFIXES:
        tokens.pop()
    return " ".join(tokens) if tokens else s

print("Building supplier clusters (parent-UEI primary, entity-UEI fallback)...")
df["normalized_name"] = df["recipient_name_raw"].apply(normalize_name)

# Cluster key priority: parent UEI (true corporate-family identity -- this
# field wasn't available to v3's NASA pipeline, so this is a genuine
# improvement over per-facility UEI fragmentation, not a v3 feature) ->
# entity UEI (strong identity, v3's primary signal) -> exact normalized name
# (rare fallback; UEI is ~100% populated in this dataset).
key_to_cluster = {}
cluster_id = 0
cluster_names = defaultdict(set)

def cluster_key(parent_uei, uei, name):
    if pd.notna(parent_uei) and parent_uei:
        return f"puei:{parent_uei}"
    if pd.notna(uei) and uei:
        return f"uei:{uei}"
    return f"name:{name}"

def get_cluster(key):
    global cluster_id
    if key in key_to_cluster:
        return key_to_cluster[key]
    cid = f"cl_{cluster_id}"; cluster_id += 1
    key_to_cluster[key] = cid
    return cid

df["_cluster_key"] = [cluster_key(p, u, n) for p, u, n in zip(df["recipient_parent_uei"], df["recipient_uei"], df["normalized_name"])]
df["cluster_id"] = df["_cluster_key"].apply(get_cluster)
cluster_parent_name = {}
for cid, name, raw, pname in zip(df["cluster_id"], df["normalized_name"], df["recipient_name_raw"], df["recipient_parent_name"]):
    cluster_names[cid].add(raw)
    if pd.notna(pname) and pname:
        cluster_parent_name[cid] = pname

# NOTE ON A REJECTED APPROACH: a blanket second-pass merge keyed on
# normalized recipient_parent_name was tried to fold split large companies
# back together, but recipient_parent_name turns out to be populated even
# for small standalone businesses (frequently just their own legal name),
# so the merge produced false positives -- e.g. "A & A CO INC" and "A & A
# HOLDINGS CORPORATION" are two unrelated real companies that both reduce
# to "A A" once generic suffix words are stripped, and would have been
# wrongly combined. That blanket approach was reverted.
#
# In its place: a small, individually-verified allow-list (below), applied
# only to specific large suppliers that were manually inspected and
# confirmed to be either (a) the exact same company differing only by a
# corporate-suffix spelling (CORP vs CORPORATION, trailing period on INC),
# or (b) a confirmed SAM.gov data error. Not applied broadly, so it carries
# none of the false-positive risk of the reverted approach.

def display_name(cid):
    if cid in cluster_parent_name:
        return cluster_parent_name[cid]
    names = cluster_names[cid]
    return max(names, key=len) if names else cid

df["normalized_supplier"] = df["cluster_id"].apply(display_name)

# Individually-verified corrections (see note above). Each entry was
# checked against its underlying raw recipient names before being added:
SUPPLIER_NAME_OVERRIDES = {
    # Same company, suffix-spelling variant only (confirmed: identical
    # cluster of Lockheed Martin awards, just "CORP" vs "CORPORATION").
    "LOCKHEED MARTIN CORPORATION": "LOCKHEED MARTIN CORP",
    # Same company, trailing-period variant only ("INC" vs "INC.").
    "L3HARRIS TECHNOLOGIES, INC.": "L3HARRIS TECHNOLOGIES, INC",
    # Same company, suffix-spelling variant only.
    "RTX CORPORATION": "RTX CORP",
    # Confirmed SAM.gov data error: recipient_parent_name for 785 awards
    # (338 raw-named "Raytheon Company", 258 "RTX BBN Technologies", 70
    # "Rockwell Collins, Inc.", 17 "RTX Corporation", 16 "Goodrich
    # Corporation", 8 "Hamilton Sundstrand Corporation", plus Pratt &
    # Whitney and Simmonds Precision entities -- all RTX Corporation's own
    # corporate family) is erroneously set to "Rockwell Collins Australia
    # Pty Limited", a much smaller Australian subsidiary. A subsidiary
    # cannot be its own parent's parent; this is a SAM.gov registration
    # error, not a real corporate structure. Awards themselves are large,
    # well-known RTX/Pratt & Whitney programs (F135 and F119 engine LRIP
    # lots, the Adaptive Engine Transition Program, TOW missile CLS).
    "ROCKWELL COLLINS AUSTRALIA PTY LIMITED": "RTX CORP",
}
df["normalized_supplier"] = df["normalized_supplier"].replace(SUPPLIER_NAME_OVERRIDES)

n_suppliers = df["normalized_supplier"].nunique()
n_raw_names = df["recipient_name_raw"].nunique()
print(f"Resolved {n_raw_names:,} raw recipient names into {n_suppliers:,} suppliers (UEI-based clustering)")

# ============================================================
# 4. TAXONOMY CLASSIFICATION (NAICS-primary, mirrors v3's taxonomy.py)
# ============================================================
print("Classifying by taxonomy...")
with open(TAXONOMY_PATH) as f:
    TAXONOMY = json.load(f)["categories"]

naics_lookup = {}  # naics_code(str) -> (category, subcategory)
keyword_lookup = []  # (category, subcategory, keyword)
for cat, spec in TAXONOMY.items():
    for sub, sub_spec in spec["subcategories"].items():
        for code in sub_spec.get("naics_codes", []):
            naics_lookup[code] = (cat, sub)
        for kw in sub_spec.get("keywords", []):
            keyword_lookup.append((cat, sub, kw))

UNCLASSIFIED_CATEGORY = "Other or Unclassified"
UNCLASSIFIED_SUBCATEGORY = "Unclassified Spend"

def classify(naics_code, psc_desc, naics_desc, txn_desc):
    if pd.notna(naics_code):
        code_str = str(int(naics_code)) if isinstance(naics_code, float) else str(naics_code)
        if code_str in naics_lookup:
            cat, sub = naics_lookup[code_str]
            return cat, sub, 0.85, f"NAICS code {code_str} matches {sub}"
    haystack = " ".join(str(x) for x in [psc_desc, naics_desc, txn_desc] if pd.notna(x)).lower()
    if haystack:
        for cat, sub, kw in keyword_lookup:
            if kw in haystack:
                return cat, sub, 0.6, f"keyword '{kw}' matched {sub}"
    return UNCLASSIFIED_CATEGORY, UNCLASSIFIED_SUBCATEGORY, 0.0, "no deterministic match"

results = df.apply(
    lambda r: classify(r["naics_code"], r["product_or_service_code_description"], r["naics_description"], r["transaction_description"]),
    axis=1
)
df["ai_spend_category"] = [r[0] for r in results]
df["ai_spend_subcategory"] = [r[1] for r in results]
df["classification_confidence"] = [r[2] for r in results]
df["classification_evidence"] = [r[3] for r in results]
df["review_status"] = df["classification_confidence"].apply(lambda c: "NEEDS_REVIEW" if c < 0.5 else "OK")

unclassified_pct = (df["ai_spend_category"] == UNCLASSIFIED_CATEGORY).mean() * 100
print(f"Unclassified: {unclassified_pct:.1f}%")
print(df["ai_spend_category"].value_counts().head(20))

# Save the cleaned/enriched dataframe for the next stage
df.to_pickle(f"{OUT_DIR}/enriched.pkl")
with open(f"{OUT_DIR}/data_quality_flags.json", "w") as f:
    json.dump({"implausible_awards_excluded": implausible_awards}, f)
print(f"\nSaved enriched dataset: {len(df):,} rows -> {OUT_DIR}/enriched.pkl")
