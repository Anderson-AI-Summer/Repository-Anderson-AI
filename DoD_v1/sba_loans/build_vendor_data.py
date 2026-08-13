# -*- coding: utf-8 -*-
import json

with open(r"C:\finances\data\sba_loans\_vendor_analysis.json") as f:
    rows = json.load(f)

TOTAL_DOD = 501544127665.41

NAME_OVERRIDES = {
    "LOCKHEED MARTIN CORPORATION": "Lockheed Martin Corporation",
    "RAYTHEON COMPANY": "Raytheon Company",
    "ELECTRIC BOAT CORPORATION": "Electric Boat Corporation",
    "THE BOEING COMPANY": "The Boeing Company",
    "NORTHROP GRUMMAN SYSTEMS CORPORATION": "Northrop Grumman Systems Corporation",
    "HUNTINGTON INGALLS INCORPORATED": "Huntington Ingalls Incorporated",
    "AMERISOURCEBERGEN DRUG CORP": "AmerisourceBergen Drug Corp",
    "RTX CORPORATION": "RTX Corporation",
    "HUMANA GOVERNMENT BUSINESS INC": "Humana Government Business Inc",
    "ATLANTIC DIVING SUPPLY, INC.": "Atlantic Diving Supply, Inc.",
    "SIKORSKY AIRCRAFT CORPORATION": "Sikorsky Aircraft Corporation",
    "LEIDOS, INC.": "Leidos, Inc.",
    "TRIWEST HEALTHCARE ALLIANCE CORP": "TriWest Healthcare Alliance Corp",
    "BOOZ ALLEN HAMILTON INC": "Booz Allen Hamilton Inc",
    "AMENTUM SERVICES, INC.": "Amentum Services, Inc.",
    "GENERAL ELECTRIC COMPANY": "General Electric Company",
    "SIERRA NEVADA COMPANY, LLC": "Sierra Nevada Company, LLC",
    "BAE SYSTEMS LAND & ARMAMENTS L.P.": "BAE Systems Land & Armaments L.P.",
    "BATH IRON WORKS CORPORATION": "Bath Iron Works Corporation",
    "BECHTEL PLANT MACHINERY, INC.": "Bechtel Plant Machinery, Inc.",
    "SCIENCE APPLICATIONS INTERNATIONAL CORPORATION": "Science Applications International Corp. (SAIC)",
    "CACI, INC. - FEDERAL": "CACI, Inc. - Federal",
    "THE JOHNS HOPKINS UNIVERSITY APPLIED PHYSICS LABORATORY LLC": "Johns Hopkins University Applied Physics Lab",
    "ECC CONSTRUCTORS LLC": "ECC Constructors LLC",
    "DELL MARKETING L.P.": "Dell Marketing L.P.",
    "FLUOR MARINE PROPULSION, LLC": "Fluor Marine Propulsion, LLC",
    "ASHBRITT INC": "AshBritt Inc",
    "L3HARRIS TECHNOLOGIES INTEGRATED SYSTEMS L.P.": "L3Harris Technologies Integrated Systems L.P.",
    "V2X SYSTEMS LLC": "V2X Systems LLC",
    "SPACE EXPLORATION TECHNOLOGIES CORP.": "Space Exploration Technologies Corp. (SpaceX)",
}

out = []
for r in rows:
    share = r["catchall_share_pct"]
    if share >= 15:
        tier = "flag"
    elif share >= 5:
        tier = "watch"
    else:
        tier = "clear"
    top_catchall = r["catchall_codes"][0]["name"] if r["catchall_codes"] else None
    out.append({
        "name": NAME_OVERRIDES.get(r["name"], r["name"].title()),
        "raw_name": r["name"],
        "total": r["total"],
        "pct_of_total": r["total"] / TOTAL_DOD * 100,
        "catchall_amt": r["catchall_amt"],
        "catchall_share": share,
        "tier": tier,
        "naics_code_count": r["naics_code_count"],
        "naics_incomplete": r["naics_has_next"],
        "top_catchall": top_catchall,
        "top_naics": r["top_naics"][0]["name"] if r["top_naics"] else None,
    })

out_sorted = sorted(out, key=lambda r: -r["total"])
with open(r"C:\finances\data\sba_loans\_vendor_tab_data.json", "w") as f:
    json.dump(out_sorted, f)

print(json.dumps(out_sorted[:3], indent=2))
print("count:", len(out_sorted))
