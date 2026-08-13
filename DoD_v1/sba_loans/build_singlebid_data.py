# -*- coding: utf-8 -*-
import json

with open(r"C:\finances\data\sba_loans\_single_bid_results.json") as f:
    d = json.load(f)

NAME_FIXES = {
    "LOCKHEED MARTIN CORP": "Lockheed Martin Corp",
    "LOCKHEED MARTIN CORPORATION": "Lockheed Martin Corporation",
    "BAE SYSTEMS HAWAII SHIPYARDS INC.": "BAE Systems Hawaii Shipyards Inc.",
    "PARSONS GOVERNMENT SERVICES INC.": "Parsons Government Services Inc.",
    "NORTHROP GRUMMAN SYSTEMS CORPORATION": "Northrop Grumman Systems Corporation",
    "RAYTHEON COMPANY": "Raytheon Company",
    "GENERAL DYNAMICS MISSION SYSTEMS, INC.": "General Dynamics Mission Systems, Inc.",
    "SERCO INC": "Serco Inc",
    "NAVMAR APPLIED SCIENCES CORP": "Navmar Applied Sciences Corp",
    "BLACK RIVER SYSTEMS COMPANY, INC.": "Black River Systems Company, Inc.",
    "SCIENCE APPLICATIONS INTERNATIONAL CORPORATION": "Science Applications International Corp. (SAIC)",
    "BAE SYSTEMS MARITIME SOLUTIONS NORFOLK INC.": "BAE Systems Maritime Solutions Norfolk Inc.",
    "DPR-RQ CONSTRUCTION, LLC": "DPR-RQ Construction, LLC",
    "GENERAL DYNAMICS-OTS, INC.": "General Dynamics-OTS, Inc.",
    "SHORE TERMINALS LLC": "Shore Terminals LLC",
    "KBR WYLE SERVICES, LLC": "KBR Wyle Services, LLC",
    "NALGE NUNC INTERNATIONAL CORPORATION": "Nalge Nunc International Corp.",
    "DCS CORPORATION": "DCS Corporation",
    "ULTRA ELECTRONICS OCEAN SYSTEMS INC.": "Ultra Electronics Ocean Systems Inc.",
    "LEIDOS, INC.": "Leidos, Inc.",
}

rollup = d["vendor_rollup"][:20]
for r in rollup:
    r["name"] = NAME_FIXES.get(r["vendor"], r["vendor"].title())

with open(r"C:\finances\data\sba_loans\_singlebid_final.json", "w") as f:
    json.dump({
        "vendor_rollup": rollup,
        "single_bid_count": d["single_bid_count"],
        "single_bid_total_value": d["single_bid_total_value"],
        "all_competed_count": d["all_competed_count"],
        "all_competed_value": d["all_competed_value"],
        "total_definitive_contracts": d["total_records"],
    }, f)

print("Top vendor:", rollup[0])
print("single_bid_count:", d["single_bid_count"], "of", d["all_competed_count"])
