# -*- coding: utf-8 -*-
import json

with open(r"C:\finances\data\sba_loans\_vendor_analysis_fullrange.json") as f:
    rows = json.load(f)

TOTAL_DOD = 2954813924288.0

NAME_OVERRIDES = {
    "LOCKHEED MARTIN CORPORATION": "Lockheed Martin Corporation",
    "THE BOEING COMPANY": "The Boeing Company",
    "RAYTHEON COMPANY": "Raytheon Company",
    "NORTHROP GRUMMAN SYSTEMS CORPORATION": "Northrop Grumman Systems Corporation",
    "ELECTRIC BOAT CORPORATION": "Electric Boat Corporation",
    "HUMANA GOVERNMENT BUSINESS INC": "Humana Government Business Inc",
    "HUNTINGTON INGALLS INCORPORATED": "Huntington Ingalls Incorporated",
    "RTX CORPORATION": "RTX Corporation",
    "PFIZER INC": "Pfizer Inc",
    "SIKORSKY AIRCRAFT CORPORATION": "Sikorsky Aircraft Corporation",
    "AMERISOURCEBERGEN DRUG CORP": "AmerisourceBergen Drug Corp",
    "ATLANTIC DIVING SUPPLY, INC.": "Atlantic Diving Supply, Inc.",
    "LEIDOS, INC.": "Leidos, Inc.",
    "GENERAL ELECTRIC COMPANY": "General Electric Company",
    "HEALTH NET FEDERAL SERVICES, LLC": "Health Net Federal Services, LLC",
    "GENERAL DYNAMICS LAND SYSTEMS INC.": "General Dynamics Land Systems Inc.",
    "BOOZ ALLEN HAMILTON INC": "Booz Allen Hamilton Inc",
    "AMENTUM SERVICES, INC.": "Amentum Services, Inc.",
    "L3HARRIS TECHNOLOGIES INTEGRATED SYSTEMS L.P.": "L3Harris Technologies Integrated Systems L.P.",
    "BECHTEL PLANT MACHINERY, INC.": "Bechtel Plant Machinery, Inc.",
    "SCIENCE APPLICATIONS INTERNATIONAL CORPORATION": "Science Applications International Corp. (SAIC)",
    "GENERAL ATOMICS AERONAUTICAL SYSTEMS, INC.": "General Atomics Aeronautical Systems, Inc.",
    "FLUOR MARINE PROPULSION, LLC": "Fluor Marine Propulsion, LLC",
    "OSHKOSH DEFENSE LLC": "Oshkosh Defense LLC",
    "SIERRA NEVADA COMPANY, LLC": "Sierra Nevada Company, LLC",
    "BAE SYSTEMS LAND & ARMAMENTS L.P.": "BAE Systems Land & Armaments L.P.",
    "BATH IRON WORKS CORPORATION": "Bath Iron Works Corporation",
    "L3HARRIS TECHNOLOGIES, INC.": "L3Harris Technologies, Inc.",
    "BELL BOEING JOINT PROJECT OFFICE": "Bell Boeing Joint Project Office",
    "GENERAL DYNAMICS MISSION SYSTEMS, INC.": "General Dynamics Mission Systems, Inc.",
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
with open(r"C:\finances\data\sba_loans\_vendor_tab_data_fullrange.json", "w") as f:
    json.dump(out_sorted, f)

print("count:", len(out_sorted))
flagged = [r for r in out_sorted if r["tier"] == "flag"]
watch = [r for r in out_sorted if r["tier"] == "watch"]
print("Flagged:", [(r["name"], round(r["catchall_share"],1)) for r in flagged])
print("Watch:", [(r["name"], round(r["catchall_share"],1)) for r in watch])
print("Top30 sum:", sum(r["total"] for r in out_sorted), f"{sum(r['total'] for r in out_sorted)/TOTAL_DOD*100:.1f}%")
