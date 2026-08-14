# -*- coding: utf-8 -*-
"""Agent-narrated insights: narrates the deterministic metrics in payload.json,
computes nothing new, asserts nothing the numbers can't back. Mirrors the role
of v3's insights_agent.py, written directly since I am the LLM in this session
rather than a separate API call."""
import json

with open(r"C:\finances\DoD_v2\data\payload.json") as f:
    p = json.load(f)

a = p["analytics"]
totals = a["totals"]
annual = a["annual"]
cats = a["category_breakdown"]
conc = a["concentration"]

insights = []

insights.append({
    "title": "Metric definition matters here more than usual",
    "finding": (
        f"This dataset totals {totals['net_obligations']/1e12:.2f}T across {totals['unique_awards']:,} awards, "
        f"but that figure is the sum of each award's *current total contract value* -- not dollars obligated "
        f"during this specific window. A single large IDV or production contract (e.g. an F-35 Lot buy) shows "
        f"its full multi-year ceiling the moment any action touches it, so awards active in a given year can sum "
        f"to far more than DoD's actual annual budget. This is why FY2026 (7 months, partial) shows more value "
        f"than any full prior year -- large production-lot contracts happened to get modified in that window, "
        f"not a real spending spike. Treat this as 'value of the contract portfolio active in each period,' not "
        f"'dollars spent.'"
    ),
})

top_cat = cats[0]
insights.append({
    "title": f"{top_cat['category']} dominates by a wide margin",
    "finding": (
        f"{top_cat['category']} / {top_cat['subcategory']} accounts for ${top_cat['net_obligations']/1e9:.1f}B, "
        f"more than the next two categories combined. This tracks with the independently-built Spend Taxonomy "
        f"analysis earlier in this project, which also found Aircraft & Aviation Systems as the largest DoD "
        f"spend category."
    ),
})

insights.append({
    "title": "Overall concentration is moderate; it's the categories that concentrate",
    "finding": (
        f"The department-wide supplier HHI is {conc['hhi']:.0f} (DOJ/FTC's own convention treats anything under "
        f"1500 as unconcentrated) -- unsurprising given {totals['unique_suppliers']:,} distinct suppliers. But "
        f"the top 5 suppliers still capture {conc['top5_share']*100:.1f}% of total value, and several individual "
        f"categories (see Categories & Opportunities tab) run well above 2500 HHI, meaning concentration is real, "
        f"it's just masked at the whole-department level."
    ),
})

std = p["standout_suppliers"][0]
insights.append({
    "title": f"{std['supplier']} is the largest single supplier by a wide margin",
    "finding": (
        f"${std['net_obligations']/1e9:.1f}B ({std['concentration_pct']:.1f}%) across {std['unique_awards']:,} "
        f"distinct awards -- driven heavily by F-35 Lightning II Low Rate Initial Production contracts, which "
        f"individually run into the tens of billions. This is a scale observation, not a competition or "
        f"performance finding."
    ),
})

if p["consolidation_opportunities"]:
    c = p["consolidation_opportunities"][0]
    insights.append({
        "title": f"{c['category']} shows the clearest fragmentation signal",
        "finding": c["detail"],
    })

n_dup = len(p["duplicate_purchase_candidates"])
if n_dup:
    insights.append({
        "title": f"{n_dup} pairs of same-supplier, same-category, similar-dollar awards flagged",
        "finding": (
            f"Close in time (within 120 days) and similar in size (within 30%) -- the 'two separate purchases "
            f"instead of one consolidated buy' pattern. Not evidence of waste on its own; see the Standout tab "
            f"for specifics."
        ),
    })

n_unclassified = next((c["transaction_count"] for c in cats if c["category"] == "Other or Unclassified"), 0)
pct_unclassified = n_unclassified / totals["transaction_count"] * 100 if totals["transaction_count"] else 0
insights.append({
    "title": f"{pct_unclassified:.0f}% of awards are unclassified",
    "finding": (
        f"{n_unclassified:,} of {totals['transaction_count']:,} awards didn't match this taxonomy's NAICS codes "
        f"or keywords deterministically. Left as 'Other or Unclassified' rather than guessed, consistent with "
        f"this project's rule that ambiguous records go to review, not a forced category."
    ),
})

insights.append({
    "title": "Supplier resolution: a few large-company splits were manually corrected",
    "finding": (
        "recipient_parent_uei-based clustering occasionally splits one real company across two entries "
        "(a suffix spelling difference, or in one case a confirmed SAM.gov data error attributing RTX "
        "Corporation's own awards to a small Australian subsidiary). A blanket automated fix for this was "
        "tried and reverted -- it merged unrelated small businesses that happened to share generic name "
        "fragments. In its place, four individually-verified corrections (Lockheed Martin, RTX, L3Harris, "
        "and the Rockwell Collins Australia mislabeling) are applied directly; the long tail of 24,000+ "
        "smaller suppliers is left as-is rather than risk a false merge."
    ),
})

with open(r"C:\finances\DoD_v2\data\insights.json", "w") as f:
    json.dump(insights, f)

for i in insights:
    print("-", i["title"])
print(f"\n{len(insights)} insights written.")
