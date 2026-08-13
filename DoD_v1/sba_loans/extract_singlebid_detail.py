# -*- coding: utf-8 -*-
import csv, glob, json

FILES = glob.glob(r"C:\finances\data\sba_loans\offers_monthly\*.csv")

def to_int(v):
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None

def to_float(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return None

GENUINELY_COMPETED = {"FULL AND OPEN COMPETITION", "FULL AND OPEN COMPETITION AFTER EXCLUSION OF SOURCES", "COMPETED UNDER SAP"}

BRANCH_SHORT = {
    "Department of the Army": "Army",
    "Department of the Air Force": "Air Force",
    "Department of the Navy": "Navy",
    "Defense Logistics Agency": "DLA",
    "Washington Headquarters Services": "WHS",
    "Defense Contract Management Agency": "DCMA",
    "Defense Commissary Agency": "DeCA",
    "Defense Health Agency": "DHA",
    "Defense Threat Reduction Agency": "DTRA",
    "U.S. Special Operations Command": "SOCOM",
    "Missile Defense Agency": "MDA",
    "Department of Defense Education Activity": "DoDEA",
    "Defense Advanced Research Projects Agency": "DARPA",
    "Defense Human Resources Activity": "DHRA",
}

records = []
for path in FILES:
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            offers = to_int(r.get("number_of_offers_received"))
            ec = (r.get("extent_competed") or "").strip().upper()
            amt = to_float(r.get("total_dollars_obligated") or r.get("current_total_value_of_award") or r.get("potential_total_value_of_award"))
            if offers == 1 and ec in GENUINELY_COMPETED and amt is not None and 0 < amt < 350000:
                sub_agency = r.get("awarding_sub_agency_name") or ""
                records.append({
                    "award_id": r.get("award_id_piid"),
                    "parent_award_id": r.get("parent_award_id_piid") or "",
                    "vendor": r.get("recipient_name"),
                    "vendor_uei": r.get("recipient_uei") or "",
                    "amount": amt,
                    "near_threshold": amt >= 300000,
                    "branch_short": BRANCH_SHORT.get(sub_agency, sub_agency or "Unknown"),
                    "awarding_sub_agency": sub_agency,
                    "awarding_office": r.get("awarding_office_name") or "",
                    "funding_agency": r.get("funding_agency_name") or "",
                    "funding_sub_agency": r.get("funding_sub_agency_name") or "",
                    "extent_competed": (r.get("extent_competed") or "").title(),
                    "solicitation_procedures": (r.get("solicitation_procedures") or "").title(),
                    "solicitation_id": r.get("solicitation_identifier") or "",
                    "type_of_contract_pricing": (r.get("type_of_contract_pricing") or "").title(),
                    "number_of_offers": offers,
                    "award_date": r.get("award_base_action_date") or "",
                    "pop_start_date": r.get("period_of_performance_start_date") or "",
                    "pop_end_date": r.get("period_of_performance_current_end_date") or "",
                    "description": r.get("prime_award_base_transaction_description") or "",
                    "psc_description": r.get("product_or_service_code_description") or "",
                    "naics_description": r.get("naics_description") or "",
                    "pop_city": r.get("primary_place_of_performance_city_name") or "",
                    "pop_state": r.get("primary_place_of_performance_state_name") or "",
                    "pop_country": r.get("primary_place_of_performance_country_name") or "",
                    "vendor_city": r.get("recipient_city_name") or "",
                    "vendor_state": r.get("recipient_state_name") or "",
                    "vendor_country": r.get("recipient_country_name") or "",
                    "place_of_manufacture": r.get("place_of_manufacture") or "",
                })

records.sort(key=lambda x: -x["amount"])
print(f"Total records: {len(records)}")
print(f"Sample record fields: {list(records[0].keys())}")
print()
for r in records[:3]:
    print(json.dumps(r, indent=2))

with open(r"C:\finances\data\sba_loans\_singlebid_detail_export.json", "w", encoding="utf-8") as f:
    json.dump(records, f)
