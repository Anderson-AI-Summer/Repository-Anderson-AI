"""Orchestrates ingestion, vendor resolution, classification, and supplier checks."""

from typing import Dict, List

from spend_agent.ingest import load_transactions
from spend_agent.models import ClassifiedTransaction
from spend_agent.supplier_check import check_preferred_supplier
from spend_agent.taxonomy import Category, load_preferred_suppliers, load_taxonomy, classify
from spend_agent.vendor_resolution import VendorCluster, build_vendor_registry, load_vendor_aliases


def run_pipeline(
    transactions_path: str,
    taxonomy_path: str,
    preferred_suppliers_path: str,
    vendor_aliases_path: str = "config/vendor_aliases.json",
) -> "tuple[List[ClassifiedTransaction], Dict[int, VendorCluster]]":
    transactions = load_transactions(transactions_path)
    taxonomy: List[Category] = load_taxonomy(taxonomy_path)
    preferred_suppliers = load_preferred_suppliers(preferred_suppliers_path)
    aliases = load_vendor_aliases(vendor_aliases_path)

    raw_to_cluster_id, clusters = build_vendor_registry(
        (t.vendor_raw for t in transactions), aliases
    )

    results: List[ClassifiedTransaction] = []
    for txn in transactions:
        cluster_id = raw_to_cluster_id[txn.vendor_raw]
        cluster = clusters[cluster_id]
        category = classify(cluster.canonical_name, txn.description, taxonomy)
        preferred, bypassed = check_preferred_supplier(
            category, cluster.canonical_name, preferred_suppliers, aliases
        )
        results.append(
            ClassifiedTransaction(
                transaction=txn,
                category=category,
                canonical_vendor=cluster.canonical_name,
                vendor_cluster_id=cluster_id,
                vendor_alias_count=len(cluster.aliases),
                preferred_supplier=preferred,
                bypassed_preferred_supplier=bypassed,
            )
        )

    return results, clusters
