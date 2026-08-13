# -*- coding: utf-8 -*-
import json

FDIR = r"C:\finances\data\sba_loans\fonts"

def b64(name):
    with open(rf"{FDIR}\{name}.b64", "r") as f:
        return f.read().strip()

SANS400 = b64("sans400")
SANS500 = b64("sans500")
SANS600 = b64("sans600")
MONO400 = b64("mono400")
MONO500 = b64("mono500")
SERIF600 = b64("serif600")

DATA = [
    {"name": "Aircraft & Aviation Systems", "amt": 104076897521, "examples": ["Aircraft Manufacturing", "Aircraft Engine & Engine Parts", "Aircraft Parts & Auxiliary Equipment"], "kind": "core"},
    {"name": "R&D and Engineering Services", "amt": 79987242736, "examples": ["Engineering Services", "R&D \u2014 Physical, Engineering & Life Sciences"], "kind": "core"},
    {"name": "Construction & Facilities Infrastructure", "amt": 39895437118, "examples": ["Commercial & Institutional Building Construction", "Heavy & Civil Engineering Construction", "Facilities Support Services"], "kind": "core"},
    {"name": "Shipbuilding & Maritime", "amt": 38832724658, "examples": ["Ship Building and Repairing", "Deep Sea Freight Transportation"], "kind": "core"},
    {"name": "Missiles, Space & Satellite Systems", "amt": 34396406145, "examples": ["Guided Missile & Space Vehicle Manufacturing", "Satellite Telecommunications"], "kind": "core"},
    {"name": "IT, Software & Computing Services", "amt": 31059854444, "examples": ["Computer Systems Design", "Software Publishers", "Computing Infrastructure & Data Processing"], "kind": "core"},
    {"name": "Electronics, Sensors & Guidance/Comm Systems", "amt": 30513245405, "examples": ["Navigation, Guidance & Instrument Mfg.", "Communications Equipment Mfg."], "kind": "core"},
    {"name": "Healthcare & Medical", "amt": 24741470790, "examples": ["Direct Health & Medical Insurance Carriers", "Medicinal & Botanical Mfg."], "kind": "core"},
    {"name": "Industrial Supplies, Equipment & MRO", "amt": 16656476091, "examples": ["Equipment & Supplies Wholesalers", "Machinery Repair & Maintenance"], "kind": "core"},
    {"name": "Professional, Management & Consulting Services", "amt": 15129380941, "examples": ["Admin & Management Consulting", "Scientific & Technical Consulting"], "kind": "core"},
    {"name": "Weapons, Ammunition & Ordnance", "amt": 13574112518, "examples": ["Ammunition Mfg.", "Explosives Mfg.", "Small Arms Mfg."], "kind": "core"},
    {"name": "Ground Vehicles & Combat Equipment", "amt": 9284438957, "examples": ["Military Armored Vehicle & Tank Mfg.", "Truck Trailer Mfg."], "kind": "core"},
    {"name": "Fuel, Energy & Petroleum", "amt": 8227204576, "examples": ["Petroleum Refineries"], "kind": "core"},
    {"name": "Environmental & Waste Management", "amt": 6394633173, "examples": ["Waste Collection", "Remediation Services", "Hazardous Waste Treatment"], "kind": "core"},
    {"name": "Food & Subsistence", "amt": 4316314539, "examples": ["Food Service Contractors", "Commercial Bakeries"], "kind": "core"},
    {"name": "Base Support Services", "amt": 2026527913, "examples": ["Janitorial Services", "Landscaping", "Security Guards & Patrol"], "kind": "core"},
    {"name": "Transportation & Logistics/Warehousing", "amt": 1674451503, "examples": ["Warehousing & Storage", "Couriers & Express Delivery"], "kind": "core"},
    {"name": "Apparel & Textiles", "amt": 1309537456, "examples": ["Cut & Sew Apparel Contractors"], "kind": "core"},
    {"name": "Other / Long-Tail NAICS + Grants & Assistance", "amt": 39447771182, "examples": ["2,000+ smaller NAICS codes", "Grants ($9.4B)", "Other assistance & direct payments"], "kind": "residual"},
]

TOTAL = sum(d["amt"] for d in DATA)
for d in DATA:
    d["pct"] = d["amt"] / TOTAL * 100

DATA_SORTED = sorted(DATA, key=lambda d: -d["amt"])

with open(r"C:\finances\data\sba_loans\_data.json", "w") as f:
    json.dump({"total": TOTAL, "rows": DATA_SORTED}, f)

print("TOTAL", TOTAL, "rows", len(DATA_SORTED))
