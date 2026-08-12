"""Agent 3: Procurement Insights Agent.

Interprets metrics *already calculated by deterministic code*
(src/analytics.py) -- it never performs arithmetic itself, only cites and
narrates numbers it is given. Constrained to cautious, evidence-grounded
language; the system prompt explicitly forbids fraud/legal claims,
invented preferred-supplier status, guaranteed savings, and fabricated
prices or terms. The deterministic fallback below follows the same rules
via rule-based templates instead of a live model call.
"""
from __future__ import annotations

import json

from pydantic import BaseModel, Field

from src.agents.base import AgentRunStats, call_claude, run_agent

PROMPT_VERSION = "insights-agent-v1"

SYSTEM_PROMPT = """You are a procurement insights analyst reviewing NASA contract spend metrics that
have ALREADY been calculated by deterministic code. You interpret and narrate these metrics --
you never perform your own arithmetic, and you never introduce a number that isn't in the
metrics you were given.

You MUST NOT:
- claim fraud, illegality, or a policy violation
- claim or imply a supplier has "preferred" status unless the data explicitly says so
- claim guaranteed or definite savings
- invent prices, performance details, or contract terms not present in the metrics
- perform your own arithmetic that should come from the deterministic metrics

Use cautious language: "potential opportunity", "warrants review", "may indicate". Every
finding must cite the exact metric(s) that support it and name the affected years, suppliers,
categories, or awards.

Respond with ONLY a JSON object matching this schema, no other text:
{"findings": [{"title": string, "description": string, "supporting_metrics": [string],
"affected_entities": [string], "confidence_language": string}]}
Return at most 6 findings. If nothing warrants a finding, return an empty findings list.
"""


class InsightFindingOut(BaseModel):
    title: str
    description: str
    supporting_metrics: list[str]
    affected_entities: list[str] = Field(default_factory=list)
    confidence_language: str = "potential opportunity — warrants review"


class InsightsOutput(BaseModel):
    findings: list[InsightFindingOut]


def _fallback_findings(metrics: dict) -> InsightsOutput:
    findings: list[InsightFindingOut] = []

    conc = metrics.get("concentration", {})
    hhi = conc.get("hhi")
    top5_share = conc.get("top5_share")
    if hhi is not None and hhi > 2500:
        findings.append(InsightFindingOut(
            title="High supplier concentration",
            description=(
                f"Supplier concentration (HHI={hhi:.0f}) is above the 2,500 threshold commonly "
                f"used to flag high concentration, with the top 5 suppliers accounting for "
                f"{(top5_share or 0) * 100:.1f}% of net obligations. This may indicate a small "
                f"supplier base for the categories involved and warrants review."
            ),
            supporting_metrics=[f"HHI={hhi:.0f}", f"top5_share={(top5_share or 0) * 100:.1f}%"],
            affected_entities=metrics.get("top_suppliers_names", [])[:5],
        ))

    deob = metrics.get("deobligation_rate")
    if deob is not None and deob > 0.05:
        findings.append(InsightFindingOut(
            title="Elevated deobligation rate",
            description=(
                f"The deobligation rate is {deob * 100:.1f}% of gross positive obligations. "
                f"This may indicate a potential opportunity to review contract modification and "
                f"closeout patterns; it is not evidence of any wrongdoing."
            ),
            supporting_metrics=[f"deobligation_rate={deob * 100:.1f}%"],
        ))

    tail = metrics.get("tail_spend_share")
    if tail is not None and tail > 0.15:
        findings.append(InsightFindingOut(
            title="Meaningful tail spend",
            description=(
                f"Approximately {tail * 100:.1f}% of net obligations sit in the long tail of "
                f"low-volume suppliers/categories, which may indicate potential fragmentation "
                f"and warrants review for consolidation opportunities."
            ),
            supporting_metrics=[f"tail_spend_share={tail * 100:.1f}%"],
        ))

    for cat_change in metrics.get("notable_category_yoy_changes", []):
        findings.append(InsightFindingOut(
            title=f"Year-over-year shift in {cat_change['category']}",
            description=(
                f"Net obligations in '{cat_change['category']}' changed {cat_change['pct_change']:+.1f}% "
                f"from FY{cat_change['from_fy']} to FY{cat_change['to_fy']}. This may indicate a "
                f"potential opportunity for further review of program-level drivers."
            ),
            supporting_metrics=[f"pct_change={cat_change['pct_change']:+.1f}%"],
            affected_entities=[cat_change["category"]],
        ))

    return InsightsOutput(findings=findings[:6])


def generate_insights(metrics: dict, stats: AgentRunStats) -> InsightsOutput:
    key_payload = {"prompt_version": PROMPT_VERSION, "metrics": metrics}

    def live_fn() -> str:
        return call_claude(SYSTEM_PROMPT, json.dumps(metrics, default=str), max_tokens=1500)

    def fallback_fn() -> InsightsOutput:
        return _fallback_findings(metrics)

    result, _mode = run_agent(stats, "insights_agent", key_payload, InsightsOutput, live_fn, fallback_fn)
    return result
