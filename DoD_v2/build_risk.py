# -*- coding: utf-8 -*-
"""
Two new procurement-risk signals, additive to the existing spend taxonomy /
vendor concentration / no-bid analyses:

1. Sole-Source Pricing Risk: crosses extent_competed with type_of_contract_pricing.
   The highest-risk combination is NOT COMPETED (no competitive price pressure)
   paired with a cost-reimbursement or time-and-materials/labor-hour pricing
   type (the contractor doesn't bear cost risk either) -- FAR 16.301-3 and
   DoD IG reports routinely flag this combination for extra oversight. This
   is a screening signal, not a finding of wrongdoing: cost-reimbursement
   contracts are explicitly permitted, often for good reasons (R&D, uncertain
   scope), and sole-source is often legally justified (see the justification
   code breakdown included here).

2. Foreign Vendor & Overseas Spend: breaks out spend by recipient_country_name
   (domestic vs foreign) and compares sole-source rates. DISCLOSED CONTEXT:
   a large share of foreign-vendor spend is structural, not suspicious --
   Status of Forces Agreements and host-nation construction rules often
   require using local firms for OCONUS base construction/services (e.g.
   Japanese contractors building on Kadena/Misawa, seen elsewhere in this
   project). This tab quantifies the pattern; it does not allege wrongdoing.
"""
import json
import pandas as pd

OUT_DIR = r"C:\finances\DoD_v2\data"
df = pd.read_pickle(f"{OUT_DIR}/enriched.pkl")

# ============================================================
# 1. SOLE-SOURCE PRICING RISK
# ============================================================
COMPETED_CODES = {"FULL AND OPEN COMPETITION", "FULL AND OPEN COMPETITION AFTER EXCLUSION OF SOURCES",
                   "COMPETED UNDER SAP", "FOLLOW ON TO COMPETED ACTION"}
NOT_COMPETED_CODES = {"NOT COMPETED", "NOT AVAILABLE FOR COMPETITION", "NOT COMPETED UNDER SAP"}

FIXED_PRICE_TYPES = {"FIRM FIXED PRICE", "FIXED PRICE LEVEL OF EFFORT", "FIXED PRICE INCENTIVE",
                      "FIXED PRICE WITH ECONOMIC PRICE ADJUSTMENT", "FIXED PRICE AWARD FEE",
                      "FIXED PRICE REDETERMINATION"}
COST_REIMB_TYPES = {"COST PLUS FIXED FEE", "COST NO FEE", "COST PLUS INCENTIVE FEE",
                     "COST PLUS AWARD FEE", "COST SHARING"}
TM_LH_TYPES = {"TIME AND MATERIALS", "LABOR HOURS"}

def competed_bucket(x):
    if x in COMPETED_CODES:
        return "Competed"
    if x in NOT_COMPETED_CODES:
        return "Not Competed"
    return "Other/Unknown"

def pricing_bucket(x):
    if x in FIXED_PRICE_TYPES:
        return "Fixed-Price"
    if x in COST_REIMB_TYPES:
        return "Cost-Reimbursement"
    if x in TM_LH_TYPES:
        return "Time & Materials / Labor-Hour"
    return "Other/Unknown"

df["_competed_bucket"] = df["extent_competed"].map(competed_bucket)
df["_pricing_bucket"] = df["type_of_contract_pricing"].map(pricing_bucket)

risk_matrix = []
for (cb, pb), g in df.groupby(["_competed_bucket", "_pricing_bucket"]):
    risk_matrix.append({
        "competed_bucket": cb, "pricing_bucket": pb,
        "amount": float(g["amount"].sum()), "count": int(len(g)),
    })
risk_matrix.sort(key=lambda r: -r["amount"])

HIGH_RISK_PRICING = {"Cost-Reimbursement", "Time & Materials / Labor-Hour"}
high_risk_mask = (df["_competed_bucket"] == "Not Competed") & (df["_pricing_bucket"].isin(HIGH_RISK_PRICING))
high_risk = df[high_risk_mask].copy()
print(f"High-risk (not competed + cost-reimb/T&M): {len(high_risk):,} awards, ${high_risk['amount'].sum():,.0f}")

# MEGA-AWARD SPLIT: the dollar total above is dominated by inherently
# sole-source major weapons systems (F-35 production lots, submarine
# construction) awarded to the one qualified manufacturer -- not a waste
# signal by itself. A $500M threshold isolates that handful of awards so
# the "below threshold" view surfaces smaller, more idiosyncratic
# sole-source cost-type awards, which are more actionable for oversight.
MEGA_THRESHOLD = 500_000_000
high_risk_mega = high_risk[high_risk["amount"] >= MEGA_THRESHOLD].copy()
high_risk_sub_mega = high_risk[high_risk["amount"] < MEGA_THRESHOLD].copy()
print(f"  of which >= ${MEGA_THRESHOLD/1e6:.0f}M (mega-primes): {len(high_risk_mega):,} awards, ${high_risk_mega['amount'].sum():,.0f}")
print(f"  of which <  ${MEGA_THRESHOLD/1e6:.0f}M (smaller/actionable): {len(high_risk_sub_mega):,} awards, ${high_risk_sub_mega['amount'].sum():,.0f}")

# Justification codes within the high-risk slice (why was it sole-sourced?)
justification_breakdown = []
for just, g in high_risk.groupby("other_than_full_and_open_competition"):
    if pd.isna(just) or not just:
        continue
    justification_breakdown.append({
        "justification": just, "amount": float(g["amount"].sum()), "count": int(len(g)),
    })
justification_breakdown.sort(key=lambda r: -r["amount"])

def group_breakdown(frame, col):
    rows = []
    for key, g in frame.groupby(col):
        rows.append({col: key, "amount": float(g["amount"].sum()), "count": int(len(g))})
    rows.sort(key=lambda r: -r["amount"])
    return rows

# Category & supplier breakdowns -- both for the full high-risk slice and
# for the sub-mega ("smaller, more actionable") slice
high_risk_by_category = group_breakdown(high_risk, "ai_spend_category")
high_risk_by_supplier = group_breakdown(high_risk, "normalized_supplier")[:25]
sub_mega_by_category = group_breakdown(high_risk_sub_mega, "ai_spend_category")
sub_mega_by_supplier = group_breakdown(high_risk_sub_mega, "normalized_supplier")[:25]

mega_awards = []
for _, r in high_risk_mega.sort_values("amount", ascending=False).iterrows():
    mega_awards.append({
        "award_id": r["award_id_piid"], "supplier": r["normalized_supplier"],
        "amount": float(r["amount"]),
        "justification": r["other_than_full_and_open_competition"] if pd.notna(r["other_than_full_and_open_competition"]) else "",
        "description": (r["transaction_description"] or "")[:200],
    })

# Full award-level detail for the high-risk slice (for the searchable table)
high_risk_awards = []
for _, r in high_risk.sort_values("amount", ascending=False).iterrows():
    high_risk_awards.append({
        "award_id": r["award_id_piid"], "supplier": r["normalized_supplier"],
        "category": r["ai_spend_category"], "pricing_type": r["type_of_contract_pricing"],
        "justification": r["other_than_full_and_open_competition"] if pd.notna(r["other_than_full_and_open_competition"]) else "",
        "amount": float(r["amount"]),
        "is_mega": bool(r["amount"] >= MEGA_THRESHOLD),
        "date": r["action_date"].date().isoformat() if pd.notna(r["action_date"]) else None,
        "awarding_sub_agency": r["awarding_sub_agency_name"],
        "description": (r["transaction_description"] or "")[:300],
    })

# ============================================================
# 2. FOREIGN VENDOR & OVERSEAS SPEND
# ============================================================
df["_is_foreign"] = df["recipient_country_name"].fillna("UNITED STATES") != "UNITED STATES"

def bucket_summary(mask):
    sub = df[mask]
    total = float(sub["amount"].sum())
    competed = float(sub.loc[sub["_competed_bucket"] == "Competed", "amount"].sum())
    not_competed = float(sub.loc[sub["_competed_bucket"] == "Not Competed", "amount"].sum())
    return {
        "total": total, "count": int(len(sub)),
        "competed_pct": (competed / total * 100) if total else 0.0,
        "not_competed_pct": (not_competed / total * 100) if total else 0.0,
    }

domestic_summary = bucket_summary(~df["_is_foreign"])
foreign_summary = bucket_summary(df["_is_foreign"])
print(f"\nDomestic: ${domestic_summary['total']:,.0f} ({domestic_summary['count']:,} awards), "
      f"{domestic_summary['not_competed_pct']:.1f}% not competed")
print(f"Foreign:  ${foreign_summary['total']:,.0f} ({foreign_summary['count']:,} awards), "
      f"{foreign_summary['not_competed_pct']:.1f}% not competed")

foreign = df[df["_is_foreign"]].copy()
country_breakdown = []
for country, g in foreign.groupby("recipient_country_name"):
    total = float(g["amount"].sum())
    not_competed = float(g.loc[g["_competed_bucket"] == "Not Competed", "amount"].sum())
    country_breakdown.append({
        "country": country, "amount": total, "count": int(len(g)),
        "not_competed_pct": (not_competed / total * 100) if total else 0.0,
    })
country_breakdown.sort(key=lambda r: -r["amount"])

foreign_category_breakdown = []
for cat, g in foreign.groupby("ai_spend_category"):
    foreign_category_breakdown.append({"category": cat, "amount": float(g["amount"].sum()), "count": int(len(g))})
foreign_category_breakdown.sort(key=lambda r: -r["amount"])

foreign_not_competed = foreign[foreign["_competed_bucket"] == "Not Competed"].copy()
print(f"Foreign + not-competed: {len(foreign_not_competed):,} awards, ${foreign_not_competed['amount'].sum():,.0f}")

foreign_awards = []
for _, r in foreign.sort_values("amount", ascending=False).iterrows():
    foreign_awards.append({
        "award_id": r["award_id_piid"], "supplier": r["normalized_supplier"],
        "country": r["recipient_country_name"], "category": r["ai_spend_category"],
        "competed_bucket": r["_competed_bucket"],
        "extent_competed": r["extent_competed"] if pd.notna(r["extent_competed"]) else "",
        "amount": float(r["amount"]),
        "date": r["action_date"].date().isoformat() if pd.notna(r["action_date"]) else None,
        "awarding_sub_agency": r["awarding_sub_agency_name"],
        "pop_country": r["primary_place_of_performance_country_name"] if pd.notna(r["primary_place_of_performance_country_name"]) else "",
        "description": (r["transaction_description"] or "")[:300],
    })

# ============================================================
# 3. CONCENTRATED VENDOR NICHES (generalized Fat Leonard-style screen)
# ============================================================
# Fat Leonard (Glenn Defense Marine Asia) was structurally: one foreign
# vendor holding a near-monopoly on a recurring service niche (ship
# husbanding at Asia-Pacific ports), sole-sourced for years. This
# generalizes that shape across every (country, spend category) niche in
# the dataset: total spend >= $2M, one vendor holds >=60% of the dollars,
# that vendor has >=3 separate awards (a recurring relationship, not a
# one-off), and >=50% of the niche's dollars are uncompeted. A screening
# heuristic, not an accusation -- most flagged niches turn out to be
# legitimate structural monopolies (a national utility, the one airport
# ground-handler, a treaty-mandated trade intermediary, a sole missile
# co-producer). Each flagged niche is annotated with that context where it
# could be independently identified from the award descriptions themselves;
# niches without an identifiable structural explanation are marked
# unverified, not cleared.
NICHE_MIN_TOTAL = 2_000_000
NICHE_MIN_SHARE = 0.60
NICHE_MIN_AWARDS = 3
NICHE_MIN_NOT_COMPETED = 0.50

# Notes are drawn from publicly documented, independently identifiable
# roles (e.g. Canadian Commercial Corporation's statutory role under the US-
# Canada Defense Production Sharing Agreement) -- not from anything in this
# dataset itself. Absence of a note does NOT mean a niche is suspicious; it
# means this project didn't have independent confirmation to cite one.
NICHE_NOTES = {
    "CANADIAN COMMERCIAL CORPORATION": (
        "Canada's Crown corporation -- the legally mandated intermediary for "
        "Canada-sourced defense trade under the US-Canada Defense Production "
        "Sharing Agreement. Structural, not a competition failure."
    ),
    "VINNELL ARABIA, LLC": (
        "Long-documented Saudi Arabian National Guard modernization/training "
        "contract Vinnell has held since the 1970s under Foreign Military Sales "
        "arrangements. Publicly known, not a new or hidden pattern."
    ),
    "RAM-SYSTEM GMBH": (
        "US-German joint venture and sole producer of the RAM (Rolling Airframe "
        "Missile) system under an international co-production agreement."
    ),
    "KONGSBERG DEFENCE & AEROSPACE AS": (
        "Norwegian sole producer of the Naval Strike Missile / Joint Strike "
        "Missile family -- a unique-source weapons technology, not a market failure."
    ),
    "NEDERLANDSE ORGANISATIE VOOR TOEGEPAST-NATUURWETENSCHAPPELIJK ONDERZOEK TNO": (
        "The Dutch national applied-research institute -- structurally similar "
        "to a US FFRDC (e.g. MITRE, RAND), which are sole-source by charter."
    ),
    "BAHRAIN AIRPORT SERVICES COMPANY (BAS) B.S.C CLOSED": (
        "The sole ground-handling operator at Bahrain's airport -- a local "
        "monopoly by circumstance, not a competition failure."
    ),
    "BALL CORPORATION": (
        "Likely a data artifact, not a true foreign-vendor pattern: Ball "
        "Aerospace was acquired by BAE Systems (UK-headquartered) in 2024, so "
        "some awards may carry a UK country tag from the parent entity rather "
        "than reflecting an actual UK vendor relationship. Worth verifying "
        "independently before drawing conclusions."
    ),
}

niche_rows = []
for (country, cat), g in df.groupby(["recipient_country_name", "ai_spend_category"]):
    total = float(g["amount"].sum())
    if total < NICHE_MIN_TOTAL:
        continue
    vendor_totals = g.groupby("normalized_supplier")["amount"].sum().sort_values(ascending=False)
    top_name = vendor_totals.index[0]
    top_share = float(vendor_totals.iloc[0] / total)
    top_award_count = int((g["normalized_supplier"] == top_name).sum())
    not_competed_pct = float(1 - (g.loc[g["_competed_bucket"] == "Competed", "amount"].sum() / total))
    n_vendors = int(g["normalized_supplier"].nunique())
    if (top_share >= NICHE_MIN_SHARE and top_award_count >= NICHE_MIN_AWARDS and
            not_competed_pct >= NICHE_MIN_NOT_COMPETED and n_vendors >= 2):
        niche_rows.append({
            "country": country, "category": cat, "total": total, "n_vendors": n_vendors,
            "top_vendor": top_name, "top_share": top_share, "top_award_count": top_award_count,
            "not_competed_pct": not_competed_pct,
            "note": NICHE_NOTES.get(top_name, ""),
        })
niche_rows.sort(key=lambda r: -r["total"])
print(f"\nFlagged concentrated niches: {len(niche_rows)}, total ${sum(r['total'] for r in niche_rows):,.0f}")

flagged_pairs = {(r["country"], r["category"]) for r in niche_rows}
niche_awards = []
for _, r in df.iterrows():
    key = (r["recipient_country_name"], r["ai_spend_category"])
    if key not in flagged_pairs:
        continue
    niche_awards.append({
        "award_id": r["award_id_piid"], "supplier": r["normalized_supplier"],
        "country": r["recipient_country_name"], "category": r["ai_spend_category"],
        "competed_bucket": r["_competed_bucket"],
        "extent_competed": r["extent_competed"] if pd.notna(r["extent_competed"]) else "",
        "amount": float(r["amount"]),
        "date": r["action_date"].date().isoformat() if pd.notna(r["action_date"]) else None,
        "awarding_sub_agency": r["awarding_sub_agency_name"],
        "description": (r["transaction_description"] or "")[:300],
    })
niche_awards.sort(key=lambda r: -r["amount"])
print(f"Niche award detail rows: {len(niche_awards):,}")

# ============================================================
# SAVE
# ============================================================
payload = {
    "meta": {
        "sole_source_methodology": (
            "Crosses extent_competed with type_of_contract_pricing. 'Not Competed' covers FPDS codes "
            "NOT COMPETED, NOT AVAILABLE FOR COMPETITION, and NOT COMPETED UNDER SAP. 'Cost-Reimbursement' "
            "and 'Time & Materials/Labor-Hour' pricing types put more cost risk on the government than "
            "Firm-Fixed-Price; combined with no competitive pressure, this is a commonly used DoD IG/GAO "
            "screening signal for extra scrutiny -- not a finding of improper payment or waste. "
            "Cost-reimbursement contracts are explicitly permitted (FAR 16.301-3) and often appropriate "
            "for R&D or uncertain-scope work; sole-source awards are frequently legally justified, "
            "shown here via the FAR justification code breakdown."
        ),
        "foreign_vendor_methodology": (
            "Compares spend to U.S.-registered vendors (recipient_country_name = UNITED STATES) against "
            "all other countries. DISCLOSED CONTEXT: a large share of foreign-vendor spend reflects "
            "Status of Forces Agreements and host-nation construction requirements at OCONUS bases "
            "(e.g. Japanese contractors building on Kadena/Misawa Air Base, seen elsewhere in this "
            "dashboard) -- local-firm use is often structurally required, not a competition failure. "
            "This tab quantifies the foreign-spend and sole-source pattern; it does not allege wrongdoing."
        ),
        "niche_methodology": (
            "A generalized version of the pattern behind the 2013 'Fat Leonard' (Glenn Defense Marine "
            "Asia) Navy scandal -- one vendor holding a near-monopoly on a recurring service niche, "
            "sole-sourced for years. This screen checks every (country, spend category) niche with at "
            f"least ${NICHE_MIN_TOTAL/1e6:.0f}M in spend and flags it if one vendor holds at least "
            f"{NICHE_MIN_SHARE*100:.0f}% of the dollars across at least {NICHE_MIN_AWARDS} separate "
            f"awards (a recurring relationship, not a one-off), with at least {NICHE_MIN_NOT_COMPETED*100:.0f}% "
            "of the niche uncompeted. A screening heuristic, not an accusation: most flagged niches are "
            "legitimate structural monopolies (a national utility, a treaty-mandated trade intermediary, "
            "a sole missile co-producer) -- annotated where independently identifiable. A niche without a "
            "note is unverified, not cleared."
        ),
    },
    "risk_matrix": risk_matrix,
    "high_risk_total": float(high_risk["amount"].sum()),
    "high_risk_count": int(len(high_risk)),
    "high_risk_share_of_total_pct": float(high_risk["amount"].sum() / df["amount"].sum() * 100),
    "mega_threshold": MEGA_THRESHOLD,
    "high_risk_mega_total": float(high_risk_mega["amount"].sum()),
    "high_risk_mega_count": int(len(high_risk_mega)),
    "high_risk_sub_mega_total": float(high_risk_sub_mega["amount"].sum()),
    "high_risk_sub_mega_count": int(len(high_risk_sub_mega)),
    "mega_awards": mega_awards,
    "sub_mega_by_category": sub_mega_by_category,
    "sub_mega_by_supplier": sub_mega_by_supplier,
    "justification_breakdown": justification_breakdown,
    "high_risk_by_category": high_risk_by_category,
    "high_risk_by_supplier": high_risk_by_supplier,
    "high_risk_awards": high_risk_awards,
    "domestic_summary": domestic_summary,
    "foreign_summary": foreign_summary,
    "country_breakdown": country_breakdown,
    "foreign_category_breakdown": foreign_category_breakdown,
    "foreign_not_competed_total": float(foreign_not_competed["amount"].sum()),
    "foreign_not_competed_count": int(len(foreign_not_competed)),
    "foreign_awards": foreign_awards,
    "niche_thresholds": {
        "min_total": NICHE_MIN_TOTAL, "min_share": NICHE_MIN_SHARE,
        "min_awards": NICHE_MIN_AWARDS, "min_not_competed": NICHE_MIN_NOT_COMPETED,
    },
    "flagged_niches": niche_rows,
    "niche_awards": niche_awards,
}

with open(f"{OUT_DIR}/risk_payload.json", "w") as f:
    json.dump(payload, f)

print(f"\nSaved risk payload to {OUT_DIR}/risk_payload.json")
print(f"high_risk_awards: {len(high_risk_awards):,}, foreign_awards: {len(foreign_awards):,}")
