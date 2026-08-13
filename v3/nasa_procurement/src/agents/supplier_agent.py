"""Agent 1: Supplier Resolution Agent.

Adjudicates fuzzy candidate pairs that deterministic clustering
(src/supplier_resolution.py) left ambiguous. Never invoked per-transaction:
deterministic UEI/DUNS/exact-name clustering handles the bulk of records,
and this agent only rules on the leftover plausible-but-uncertain pairs.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from src.agents.base import AgentRunStats, call_claude, run_agent
from src.supplier_resolution import FuzzyCandidate, adjudicate_fallback

PROMPT_VERSION = "supplier-agent-v1"

SYSTEM_PROMPT = """You are a supplier-identity adjudicator for a NASA procurement dataset.
You are given two normalized supplier name variants that a fuzzy-matching step flagged as
*possibly* the same company. Decide whether they represent the same legal supplier.

Rules:
- Only say they are the same company if you are confident based on the names alone
  (e.g. one is clearly a shortened or reformatted version of the other).
- Do NOT merge companies just because they share a common industry word or a generic
  leading word (e.g. "First National Bank" vs "First Republic Bank" are DIFFERENT companies).
- If uncertain, say they are NOT the same and set needs_review true.

Respond with ONLY a JSON object matching this schema, no other text:
{"same_supplier": bool, "confidence": float (0-1), "evidence": string (<=200 chars), "needs_review": bool}
"""


class AdjudicationResult(BaseModel):
    same_supplier: bool
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str
    needs_review: bool = False


def adjudicate(candidate: FuzzyCandidate, stats: AgentRunStats) -> tuple[bool, float, str]:
    key_payload = {
        "prompt_version": PROMPT_VERSION,
        "name_a": candidate.name_a,
        "name_b": candidate.name_b,
        "similarity": round(candidate.similarity, 1),
        "prefix_rule_holds": candidate.prefix_rule_holds,
    }

    def live_fn() -> str:
        user = (
            f"Name A: {candidate.name_a}\n"
            f"Name B: {candidate.name_b}\n"
            f"Fuzzy similarity score: {candidate.similarity:.0f}/100\n"
            f"Whole-token prefix rule holds: {candidate.prefix_rule_holds}\n"
        )
        return call_claude(SYSTEM_PROMPT, user, max_tokens=300)

    def fallback_fn() -> AdjudicationResult:
        merge, confidence, evidence = adjudicate_fallback(candidate)
        return AdjudicationResult(same_supplier=merge, confidence=confidence, evidence=evidence, needs_review=not merge)

    result, _mode = run_agent(stats, "supplier_agent", key_payload, AdjudicationResult, live_fn, fallback_fn)
    return result.same_supplier, result.confidence, result.evidence
