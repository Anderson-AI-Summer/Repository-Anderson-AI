"""Clean transactions -> Enriched transactions.

Orchestrates: signed-obligation derivation, cumulative award obligation,
negative-obligation flags, supplier resolution (deterministic clustering +
Agent 1 adjudication of ambiguous fuzzy candidates), and spend
classification (deterministic PSC/NAICS/keyword pass + Agent 2 for the
ambiguous remainder).
"""
from __future__ import annotations

import logging

from src.agents.base import AgentRunStats
from src.agents.classification_agent import classify as agent_classify
from src.agents.supplier_agent import adjudicate as agent_adjudicate
from src.obligations import (
    compute_cumulative_award_obligation,
    detect_reversal_pairs,
    flag_negative_obligation_anomalies,
)
from src.schema import CleanTransaction, EnrichedTransaction, ObligationDirection, ReviewStatus
from src.supplier_resolution import build_base_clusters, generate_fuzzy_candidates
from src.taxonomy import classify_deterministic

logger = logging.getLogger("enrich")


def resolve_suppliers(transactions: list[CleanTransaction], stats: AgentRunStats) -> dict[str, dict]:
    """Returns {transaction_id: {"name": str, "confidence": float, "evidence": str, "needs_review": bool}}"""
    records = [
        {"raw_name": t.recipient_name_raw, "uei": t.recipient_uei, "duns": t.recipient_duns}
        for t in transactions
    ]
    clusters = build_base_clusters(records)
    by_norm_and_ids: dict[tuple, object] = {}
    for c in clusters:
        by_norm_and_ids[c.cluster_id] = c

    candidates = generate_fuzzy_candidates(clusters)
    merge_map: dict[str, str] = {}  # cluster_id -> cluster_id it merges into
    adjudications: dict[tuple[str, str], tuple[bool, float, str]] = {}
    for cand in candidates:
        same, confidence, evidence = agent_adjudicate(cand, stats)
        adjudications[(cand.cluster_a, cand.cluster_b)] = (same, confidence, evidence)
        if same:
            merge_map[cand.cluster_b] = cand.cluster_a

    def resolve_root(cid: str) -> str:
        seen = set()
        while cid in merge_map and cid not in seen:
            seen.add(cid)
            cid = merge_map[cid]
        return cid

    cluster_by_name_uei_duns: dict[tuple, str] = {}
    for c in clusters:
        cluster_by_name_uei_duns[(c.uei, c.duns, c.normalized_name)] = c.cluster_id

    result: dict[str, dict] = {}
    from src.supplier_resolution import normalize_name

    for t in transactions:
        norm = normalize_name(t.recipient_name_raw)
        key = (t.recipient_uei or None, t.recipient_duns or None, norm)
        cid = cluster_by_name_uei_duns.get(key)
        if cid is None:
            for c in clusters:
                if t.recipient_uei and c.uei == t.recipient_uei:
                    cid = c.cluster_id
                    break
                if not t.recipient_uei and c.normalized_name == norm and not c.uei:
                    cid = c.cluster_id
                    break
        root_id = resolve_root(cid) if cid else None
        cluster = by_norm_and_ids.get(root_id) if root_id else None
        if cluster is None:
            result[t.transaction_id] = {
                "name": t.recipient_name_raw,
                "confidence": 0.5,
                "evidence": "No cluster resolved; used raw name as-is",
                "needs_review": True,
            }
            continue
        result[t.transaction_id] = {
            "name": cluster.display_name(),
            "confidence": cluster.confidence,
            "evidence": cluster.evidence,
            "needs_review": cluster.confidence < 0.6,
        }
    return result


def classify_transactions(transactions: list[CleanTransaction], stats: AgentRunStats) -> dict[str, dict]:
    result: dict[str, dict] = {}
    seen_cache: dict[tuple, dict] = {}
    for t in transactions:
        det = classify_deterministic(t.psc_code, t.psc_description, t.naics_code, t.naics_description, t.transaction_description)
        if det is not None:
            category, subcategory, confidence, evidence = det
            result[t.transaction_id] = {
                "category": category, "subcategory": subcategory,
                "confidence": confidence, "evidence": evidence, "needs_review": False,
            }
            continue

        dedup_key = (t.psc_code, t.naics_code, (t.transaction_description or "")[:300])
        if dedup_key in seen_cache:
            result[t.transaction_id] = seen_cache[dedup_key]
            continue

        agent_result = agent_classify(t.psc_code, t.psc_description, t.naics_code, t.naics_description, t.transaction_description, stats)
        entry = {
            "category": agent_result.category, "subcategory": agent_result.subcategory,
            "confidence": agent_result.confidence, "evidence": agent_result.evidence,
            "needs_review": agent_result.needs_review,
        }
        seen_cache[dedup_key] = entry
        result[t.transaction_id] = entry
    return result


def enrich_transactions(transactions: list[CleanTransaction], stats: AgentRunStats | None = None) -> list[EnrichedTransaction]:
    stats = stats or AgentRunStats()

    cumulative = compute_cumulative_award_obligation(transactions)
    reversal_ids = detect_reversal_pairs(transactions)
    supplier_map = resolve_suppliers(transactions, stats)
    classification_map = classify_transactions(transactions, stats)

    # Preceding positive totals per award, for anomaly flagging.
    by_award: dict[str, list[CleanTransaction]] = {}
    for t in transactions:
        by_award.setdefault(t.award_id_piid, []).append(t)
    for award_id, txns in by_award.items():
        txns.sort(key=lambda t: (t.action_date, t.modification_number or "0"))

    enriched: list[EnrichedTransaction] = []
    for t in transactions:
        amount = t.transaction_obligated_amount
        direction = (
            ObligationDirection.OBLIGATION if amount > 0
            else ObligationDirection.DEOBLIGATION if amount < 0
            else ObligationDirection.ZERO_DOLLAR_ACTION
        )

        data_quality_flags: list[str] = []
        opportunity_flags: list[str] = []

        if direction == ObligationDirection.DEOBLIGATION:
            award_txns = by_award[t.award_id_piid]
            idx = next(i for i, x in enumerate(award_txns) if x.transaction_id == t.transaction_id)
            preceding_positive = sum(x.transaction_obligated_amount for x in award_txns[:idx] if x.transaction_obligated_amount > 0)
            data_quality_flags.extend(flag_negative_obligation_anomalies(t, cumulative[t.transaction_id], preceding_positive))

        if t.transaction_id in reversal_ids:
            data_quality_flags.append("same_day_reversal_pair")

        if not t.award_detail_available:
            data_quality_flags.append("award_detail_unavailable")

        supplier = supplier_map[t.transaction_id]
        classification = classification_map[t.transaction_id]

        needs_review = supplier["needs_review"] or classification["needs_review"] or bool(data_quality_flags)
        if classification["category"] == "Other or Unclassified":
            opportunity_flags.append("unclassified_spend")

        enriched.append(EnrichedTransaction(
            **t.model_dump(),
            transaction_obligation_signed=amount,
            transaction_obligation_absolute=abs(amount),
            obligation_direction=direction,
            cumulative_award_obligation=cumulative[t.transaction_id],
            normalized_supplier=supplier["name"],
            supplier_resolution_confidence=supplier["confidence"],
            supplier_resolution_evidence=supplier["evidence"],
            ai_spend_category=classification["category"],
            ai_spend_subcategory=classification["subcategory"],
            classification_confidence=classification["confidence"],
            classification_evidence=classification["evidence"],
            review_status=ReviewStatus.NEEDS_REVIEW if needs_review else ReviewStatus.OK,
            opportunity_flags=opportunity_flags,
            data_quality_flags=data_quality_flags,
        ))
    return enriched
