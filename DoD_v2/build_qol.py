# -*- coding: utf-8 -*-
"""
Quality-of-life contract analysis by service branch, with spend-per-servicemember.

METHODOLOGY DISCLOSURES (surfaced in the dashboard, not just here):
1. QoL categories are identified by keyword matching against each award's
   transaction description / PSC description / NAICS description -- the same
   deterministic, disclosed approach used for the main spend taxonomy. Awards
   that don't literally mention a QoL-coded facility/service are not counted,
   even if they indirectly benefit quality of life (e.g. base infrastructure).
2. FPDS's awarding_sub_agency_name does not distinguish Space Force from Air
   Force (Space Force is organizationally part of the Department of the Air
   Force and shares its contracting offices), or Marine Corps from Navy
   (Marine Corps is part of the Department of the Navy). Branches are
   reported as combined pairs for this reason: "Air Force / Space Force" and
   "Navy / Marine Corps". Army stands alone.
3. Per-servicemember figures divide a ~6.58-year cumulative spend total
   (FY2020-FY2026 YTD, Oct 2019-Apr 2026) by a single point-in-time headcount
   snapshot (Sept 30, 2025) -- not an annual budget divided by a matching
   year's headcount. An annualized rate (total / 6.58 years / headcount) is
   also computed to make cross-branch comparison more apples-to-apples.
4. Headcount source: Air & Space Forces Magazine's 2026 USAF/USSF Almanac,
   "DOD Total Force End Strength," as of Sept. 30, 2025 (same table, same
   rounding convention, for all five services).
"""
import json
import pandas as pd
import datetime as dt

OUT_DIR = r"C:\finances\DoD_v2\data"
df = pd.read_pickle(f"{OUT_DIR}/enriched.pkl")

# ============================================================
# 1. QoL CATEGORY CLASSIFICATION (keyword-based, same method as main taxonomy)
# ============================================================
QOL_KEYWORDS = {
    "Dining Facilities": ["dining facility", "dfac", "food service", "galley"],
    "Chapels": ["chapel"],
    "Family Housing": ["family housing", "military housing", "housing privatization"],
    "Dormitories / Barracks": ["dormitory", "dormitories", "barracks", "unaccompanied housing"],
    "Fitness & Recreation": ["fitness center", "gymnasium", "recreation center", "athletic facility"],
    "Child & Youth Services": ["child development center", "youth center", "child care", "youth programs", " cdc "],
    "Medical Clinics": ["medical clinic", "base hospital", "medical treatment facility"],
    "Commissary / Exchange": ["commissary", "exchange facility", "aafes", "nex "],
    "Morale, Welfare & Recreation": ["morale, welfare", "morale welfare", " mwr "],
}

text_cols = ["transaction_description", "product_or_service_code_description", "naics_description"]
haystack = df[text_cols].fillna("").agg(" ".join, axis=1).str.lower()

def classify_qol(text):
    for cat, kws in QOL_KEYWORDS.items():
        for kw in kws:
            if kw in text:
                return cat
    return None

df["_qol_category"] = haystack.apply(classify_qol)
qol = df[df["_qol_category"].notna()].copy()
print(f"QoL-classified awards: {len(qol):,} of {len(df):,} total, ${qol['amount'].sum():,.0f}")

# ============================================================
# 2. BRANCH MAPPING (disclosed combined-service limitation)
# ============================================================
BRANCH_MAP = {
    "Department of the Army": "Army",
    "Department of the Navy": "Navy / Marine Corps",
    "Department of the Air Force": "Air Force / Space Force",
}
df["_branch"] = df["awarding_sub_agency_name"].map(BRANCH_MAP).fillna("Defense-Wide / Multi-Service")
qol["_branch"] = qol["awarding_sub_agency_name"].map(BRANCH_MAP).fillna("Defense-Wide / Multi-Service")

HEADCOUNT = {
    "Army": 445_000,
    "Navy / Marine Corps": 328_000 + 173_000,
    "Air Force / Space Force": 312_000 + 9_000,
}
HEADCOUNT_DETAIL = {
    "Army": {"Army": 445_000},
    "Navy / Marine Corps": {"Navy": 328_000, "Marine Corps": 173_000},
    "Air Force / Space Force": {"Air Force": 312_000, "Space Force": 9_000},
}
HEADCOUNT_SOURCE = ("Air & Space Forces Magazine, \"2026 USAF & USSF Almanac: DOD Personnel,\" "
                    "DOD Total Force End Strength table, as of Sept. 30, 2025.")

DATA_PERIOD_START = dt.date(2019, 10, 1)
DATA_PERIOD_END = dt.date(2026, 4, 30)
YEARS_COVERED = (DATA_PERIOD_END - DATA_PERIOD_START).days / 365.25

# ============================================================
# 2B. BENEFICIARY ADJUSTMENT (disclosed, partial correction)
# ============================================================
# The awarding agency is not always the beneficiary: the Army (via the Army
# Corps of Engineers) executes a large share of DoD-wide military
# construction, including barracks/dormitories/child care centers built FOR
# Air Force or Marine Corps personnel. A spot-check found $772M of
# Army-bucketed QoL spend explicitly names another service in its own
# description (e.g. "AIRMEN DORMITORY", "MARINE CORPS BARRACKS ... KADENA
# AB", "CHILD DEVELOPMENT CENTER AT LACKLAND AIR FORCE BASE"). This is a
# FLOOR, not a full correction: it only catches awards that happen to name
# the beneficiary service in free text, so unnamed cases (very likely the
# majority) still sit in the awarding agency's bucket. Reassignment is only
# applied where a beneficiary marker is unambiguous.
BENEFICIARY_MARKERS = {
    "Air Force / Space Force": ["airmen", "air force", " afb", "usaf", " space force", "usafa"],
    "Navy / Marine Corps": ["marine corps", " usmc", "mcas ", " navy", "naval station", "naval air", " nas "],
    "Army": [" army", "soldier", "fort ", " usma", "west point"],
}

def detect_beneficiary(text, current_branch):
    for branch, markers in BENEFICIARY_MARKERS.items():
        if branch == current_branch:
            continue
        if any(m in text for m in markers):
            return branch
    return current_branch

qol_text = qol[text_cols].fillna("").agg(" ".join, axis=1).str.lower()
qol["_branch_adjusted"] = [
    detect_beneficiary(t, b) for t, b in zip(qol_text, qol["_branch"])
]
n_reassigned = int((qol["_branch_adjusted"] != qol["_branch"]).sum())
reassigned_value = float(qol.loc[qol["_branch_adjusted"] != qol["_branch"], "amount"].sum())
print(f"\nBeneficiary-adjusted: {n_reassigned} awards (${reassigned_value:,.0f}) reassigned off their awarding branch")
print(qol.loc[qol['_branch_adjusted'] != qol['_branch'], ['_branch', '_branch_adjusted']].value_counts())

# ============================================================
# 3. BRANCH SUMMARY (QoL total, per-capita, category mix)
# ============================================================
def build_branch_row(branch, qol_col):
    b_qol = qol[qol[qol_col] == branch]
    b_total = df[df["_branch"] == branch]  # total branch spend denominator stays as-awarded (no adjustment data for non-QoL spend)
    qol_total = float(b_qol["amount"].sum())
    branch_total = float(b_total["amount"].sum())
    headcount = HEADCOUNT.get(branch)
    return {
        "branch": branch,
        "qol_total": qol_total,
        "qol_award_count": int(len(b_qol)),
        "branch_total_spend": branch_total,
        "qol_share_of_branch_pct": (qol_total / branch_total * 100) if branch_total else 0.0,
        "headcount": headcount,
        "headcount_detail": HEADCOUNT_DETAIL.get(branch),
        "qol_per_servicemember_total": (qol_total / headcount) if headcount else None,
        "qol_per_servicemember_per_year": (qol_total / headcount / YEARS_COVERED) if headcount else None,
    }

branches = ["Army", "Navy / Marine Corps", "Air Force / Space Force", "Defense-Wide / Multi-Service"]
branch_summary = [build_branch_row(b, "_branch") for b in branches]
branch_summary_adjusted = [build_branch_row(b, "_branch_adjusted") for b in branches]

branch_summary.sort(key=lambda r: -(r["qol_per_servicemember_per_year"] or 0))
branch_summary_adjusted.sort(key=lambda r: -(r["qol_per_servicemember_per_year"] or 0))

print()
print("AS-AWARDED (by contracting agency):")
print(f"{'Branch':30s} {'QoL Total':>16s} {'Headcount':>10s} {'$/person':>10s} {'$/person/yr':>12s}")
for r in branch_summary:
    hc = f"{r['headcount']:,}" if r["headcount"] else "n/a"
    pp = f"${r['qol_per_servicemember_total']:,.0f}" if r["qol_per_servicemember_total"] else "n/a"
    ppy = f"${r['qol_per_servicemember_per_year']:,.0f}" if r["qol_per_servicemember_per_year"] else "n/a"
    print(f"{r['branch']:30s} {r['qol_total']:16,.0f} {hc:>10s} {pp:>10s} {ppy:>12s}")

print()
print("BENEFICIARY-ADJUSTED (floor correction, catches only explicit mentions):")
print(f"{'Branch':30s} {'QoL Total':>16s} {'Headcount':>10s} {'$/person':>10s} {'$/person/yr':>12s}")
for r in branch_summary_adjusted:
    hc = f"{r['headcount']:,}" if r["headcount"] else "n/a"
    pp = f"${r['qol_per_servicemember_total']:,.0f}" if r["qol_per_servicemember_total"] else "n/a"
    ppy = f"${r['qol_per_servicemember_per_year']:,.0f}" if r["qol_per_servicemember_per_year"] else "n/a"
    print(f"{r['branch']:30s} {r['qol_total']:16,.0f} {hc:>10s} {pp:>10s} {ppy:>12s}")

# ============================================================
# 4. CATEGORY BREAKDOWN BY BRANCH (matrix)
# ============================================================
category_matrix = []
for cat in QOL_KEYWORDS:
    row = {"category": cat}
    for branch in ["Army", "Navy / Marine Corps", "Air Force / Space Force", "Defense-Wide / Multi-Service"]:
        sub = qol[(qol["_branch"] == branch) & (qol["_qol_category"] == cat)]
        row[branch] = float(sub["amount"].sum())
    row["total"] = sum(v for k, v in row.items() if k != "category")
    category_matrix.append(row)
category_matrix.sort(key=lambda r: -r["total"])

# ============================================================
# 5. FULL QOL AWARD DETAIL (every classified award, for the searchable
#    detail table -- not just a top-N sample)
# ============================================================
qol_award_rows = []
for _, r in qol.sort_values("amount", ascending=False).iterrows():
    qol_award_rows.append({
        "award_id": r["award_id_piid"],
        "supplier": r["normalized_supplier"],
        "branch": r["_branch"],
        "branch_adjusted": r["_branch_adjusted"],
        "category": r["_qol_category"],
        "amount": float(r["amount"]),
        "date": r["action_date"].date().isoformat() if pd.notna(r["action_date"]) else None,
        "extent_competed": r.get("extent_competed", ""),
        "awarding_sub_agency": r["awarding_sub_agency_name"],
        "description": (r["transaction_description"] or "")[:300],
    })
print(f"Full QoL award detail rows: {len(qol_award_rows):,}")

# ============================================================
# 6. ANNUAL QOL TREND BY BRANCH
# ============================================================
qol_annual = []
for (fy, branch), g in qol.groupby(["fiscal_year", "_branch"]):
    qol_annual.append({"fiscal_year": int(fy), "branch": branch, "amount": float(g["amount"].sum())})
qol_annual.sort(key=lambda r: (r["fiscal_year"], r["branch"]))

# ============================================================
# SAVE
# ============================================================
payload = {
    "meta": {
        "methodology": (
            "Quality-of-life categories are identified by keyword matching against each award's "
            "description, PSC description, and NAICS description -- the same deterministic approach "
            "used elsewhere in this project. FPDS does not distinguish Space Force from Air Force, or "
            "Marine Corps from Navy, at the awarding_sub_agency_name level, so branches are reported as "
            "combined pairs: 'Air Force / Space Force' and 'Navy / Marine Corps'. Army is reported alone. "
            "Per-servicemember figures divide a ~6.6-year cumulative spend total by a single point-in-time "
            "headcount snapshot, not a matched annual budget -- treat as a rough comparative rate, not a "
            "precise per-person budget line."
        ),
        "headcount_source": HEADCOUNT_SOURCE,
        "data_period_start": DATA_PERIOD_START.isoformat(),
        "data_period_end": DATA_PERIOD_END.isoformat(),
        "years_covered": round(YEARS_COVERED, 2),
        "categories_tracked": list(QOL_KEYWORDS.keys()),
    },
    "branch_summary": branch_summary,
    "branch_summary_adjusted": branch_summary_adjusted,
    "beneficiary_adjustment": {
        "awards_reassigned": n_reassigned,
        "value_reassigned": reassigned_value,
        "note": (
            "A floor correction: only awards whose own description explicitly names a "
            "different service (e.g. 'AIRMEN DORMITORY', 'MARINE CORPS BARRACKS ... KADENA AB') "
            "are reassigned from the awarding branch to the named beneficiary. Most "
            "Army Corps of Engineers construction for other services doesn't name the "
            "beneficiary in the description, so this understates the true effect."
        ),
    },
    "category_matrix": category_matrix,
    "qol_awards": qol_award_rows,
    "qol_annual_by_branch": qol_annual,
    "qol_total_all_branches": float(qol["amount"].sum()),
    "qol_award_count_all_branches": int(len(qol)),
}

with open(f"{OUT_DIR}/qol_payload.json", "w") as f:
    json.dump(payload, f)

print(f"\nSaved QoL payload to {OUT_DIR}/qol_payload.json")
