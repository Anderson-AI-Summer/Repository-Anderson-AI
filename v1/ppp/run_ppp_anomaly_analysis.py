"""Statistical anomaly analysis of PPP loan data.

Replicates, at small scale, the peer-group comparison method of
Griffin, Kruger & Mahajan (2023, Journal of Finance), "Did FinTech Lenders
Facilitate PPP Fraud?" — comparing loan characteristics between fintech/
non-bank lenders and traditional banks using statistical tests, rather than
an arbitrary weighted point score.

Two per-loan statistics:
  - amount_zscore: how many standard deviations a loan's amount is from the
    mean amount for its NAICS industry category (peer-group benchmark).
  - salary_cap_implied: True if the loan's amount, divided by the reported
    jobs retained, implies (almost) every employee earns exactly the PPP
    $100,000 salary cap used in the loan formula — the specific red flag
    Griffin et al. used, since real payroll is very rarely at the cap for
    (nearly) every employee.

Two group-level tests (fintech-associated lenders vs. traditional banks):
  - Welch's t-test on amount z-scores
  - Two-proportion z-tests on the outlier and salary-cap-implied rates

See spend_agent/ppp_lender_type.py for the citation behind the lender list,
and spend_agent/ppp_stats.py for the (dependency-free, scipy-verified)
statistics implementation.

Usage:
    python3 ppp/run_ppp_anomaly_analysis.py <raw_ppp_csv> --outdir ppp/out
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spend_agent.ppp_lender_type import FINTECH, TRADITIONAL, classify_lender_type
from spend_agent.ppp_stats import mean, stdev, two_proportion_z_test, welch_t_test, zscore
from spend_agent.vendor_resolution import build_vendor_registry, load_vendor_aliases

OUTLIER_Z_THRESHOLD = 2.0
SALARY_CAP = 100_000.0
SALARY_CAP_TOLERANCE = 500.0


def _naics_category_map(taxonomy_path: str) -> dict:
    with open(taxonomy_path, encoding="utf-8") as fh:
        data = json.load(fh)
    prefix_to_category = {}
    for entry in data["categories"]:
        for kw in entry["keywords"]:
            prefix_to_category[kw.replace("naics ", "").strip()] = entry["name"]
    return prefix_to_category


def load_raw_loans(path: str) -> list:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def build_loan_records(raw_rows: list, prefix_to_category: dict, clusters, raw_to_cluster_id) -> list:
    loans = []
    for r in raw_rows:
        lender_raw = (r.get("Lender") or "").strip()
        amount_raw = (r.get("LoanAmount") or "").strip()
        if not lender_raw or not amount_raw:
            continue
        naics = (r.get("NAICSCode") or "").strip()
        category = prefix_to_category.get(naics[:2], "Uncategorized")
        jobs_raw = (r.get("JobsRetained") or "").strip()
        jobs_retained = float(jobs_raw) if jobs_raw else None
        cluster = clusters[raw_to_cluster_id[lender_raw]]

        loans.append(
            {
                "date": (r.get("DateApproved") or "").strip(),
                "lender": cluster.canonical_name,
                "lender_type": classify_lender_type(cluster.canonical_name),
                "city": (r.get("City") or "").strip(),
                "naics": naics,
                "category": category,
                "jobs_retained": jobs_retained,
                "amount": float(amount_raw),
            }
        )
    return loans


def annotate_statistics(loans: list) -> None:
    by_category = defaultdict(list)
    for loan in loans:
        by_category[loan["category"]].append(loan["amount"])
    category_stats = {cat: (mean(amts), stdev(amts)) for cat, amts in by_category.items()}

    for loan in loans:
        cat_mean, cat_stdev = category_stats[loan["category"]]
        loan["amount_zscore"] = round(zscore(loan["amount"], cat_mean, cat_stdev), 3)
        loan["statistical_outlier"] = abs(loan["amount_zscore"]) > OUTLIER_Z_THRESHOLD

        loan["round_dollar"] = loan["amount"] % 1000 == 0

        jobs = loan["jobs_retained"]
        if jobs and jobs > 0:
            implied_annual_salary = loan["amount"] / (jobs * (2.5 / 12))
            loan["salary_cap_implied"] = abs(implied_annual_salary - SALARY_CAP) <= SALARY_CAP_TOLERANCE
        else:
            loan["salary_cap_implied"] = False


def group_comparison(loans: list) -> dict:
    fintech = [l for l in loans if l["lender_type"] == FINTECH]
    bank = [l for l in loans if l["lender_type"] == TRADITIONAL]

    result = {"n_fintech": len(fintech), "n_bank": len(bank)}

    t_result = welch_t_test([l["amount_zscore"] for l in fintech], [l["amount_zscore"] for l in bank])
    result["zscore_ttest"] = t_result

    for flag in ["statistical_outlier", "salary_cap_implied", "round_dollar"]:
        count_fintech = sum(1 for l in fintech if l[flag])
        count_bank = sum(1 for l in bank if l[flag])
        result[flag] = two_proportion_z_test(count_fintech, len(fintech), count_bank, len(bank))

    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Path to a raw SBA PPP FOIA CSV (under-$150K tier)")
    parser.add_argument("--outdir", default="ppp/out", help="Directory to write output to")
    args = parser.parse_args(argv)
    os.makedirs(args.outdir, exist_ok=True)

    raw_rows = load_raw_loans(args.input)
    prefix_to_category = _naics_category_map("config/ppp_taxonomy.json")
    aliases = load_vendor_aliases("config/vendor_aliases.json")
    raw_to_cluster_id, clusters = build_vendor_registry(
        (r["Lender"].strip() for r in raw_rows if r.get("Lender")), aliases
    )

    loans = build_loan_records(raw_rows, prefix_to_category, clusters, raw_to_cluster_id)
    annotate_statistics(loans)

    out_path = os.path.join(args.outdir, "anomaly_scored_loans.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["date", "lender", "lender_type", "city", "naics", "category", "jobs_retained",
             "amount", "amount_zscore", "statistical_outlier", "salary_cap_implied", "round_dollar"]
        )
        for l in loans:
            writer.writerow(
                [
                    l["date"], l["lender"], l["lender_type"], l["city"], l["naics"], l["category"],
                    l["jobs_retained"] if l["jobs_retained"] is not None else "",
                    f'{l["amount"]:.2f}', l["amount_zscore"],
                    "yes" if l["statistical_outlier"] else "no",
                    "yes" if l["salary_cap_implied"] else "no",
                    "yes" if l["round_dollar"] else "no",
                ]
            )

    cmp = group_comparison(loans)

    print(f"Scored {len(loans)} loans.")
    print(f"Fintech/non-bank lenders: {cmp['n_fintech']} loans. Traditional banks/CUs: {cmp['n_bank']} loans.")
    print()

    t = cmp["zscore_ttest"]
    if t:
        print(f"Amount z-score, Welch's t-test: t={t.t_statistic:.3f}, df={t.df:.1f}, p={t.p_value:.4f}")
        print(f"  mean z-score (fintech) = {t.mean_a:.3f}, mean z-score (bank) = {t.mean_b:.3f}")
    else:
        print("Amount z-score t-test: insufficient sample size in one group.")

    for flag in ["statistical_outlier", "salary_cap_implied", "round_dollar"]:
        r = cmp[flag]
        if r:
            print(
                f"{flag}: fintech rate={r.rate_a:.1%} (n={r.n_a}), bank rate={r.rate_b:.1%} (n={r.n_b}), "
                f"z={r.z_statistic:.3f}, p={r.p_value:.4f}"
            )
        else:
            print(f"{flag}: insufficient sample size in one group.")

    print()
    print(f"Output written to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
