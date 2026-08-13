import pytest
from pydantic import ValidationError

from src.agents.classification_agent import ClassificationOutput, classify
from src.agents.base import AgentRunStats
from src.agents.insights_agent import InsightsOutput, _fallback_findings
from src.schema import ClassificationResult, InsightFinding, SupplierResolutionResult


def test_supplier_resolution_result_rejects_out_of_range_confidence():
    with pytest.raises(ValidationError):
        SupplierResolutionResult(raw_name="X", canonical_supplier="X", confidence=1.5, evidence="e")


def test_classification_result_rejects_negative_confidence():
    with pytest.raises(ValidationError):
        ClassificationResult(category="A", subcategory="B", confidence=-0.1, evidence="e")


def test_insight_finding_requires_supporting_metrics_field():
    with pytest.raises(ValidationError):
        InsightFinding(title="t", description="d")  # missing supporting_metrics


def test_classification_agent_routes_invalid_agent_output_to_review():
    # No live agent available in test env -> deterministic fallback path,
    # which must always produce a taxonomy-valid (category, subcategory) pair.
    stats = AgentRunStats()
    result = classify(None, None, None, None, "completely ambiguous text", stats)
    assert isinstance(result, ClassificationOutput)
    assert result.needs_review is True
    from src.taxonomy import validate_classification
    assert validate_classification(result.category, result.subcategory) is True


def test_insights_fallback_never_uses_forbidden_language():
    metrics = {
        "concentration": {"hhi": 5000, "top5_share": 0.8},
        "deobligation_rate": 0.2,
        "tail_spend_share": 0.3,
        "top_suppliers_names": ["ACME"],
        "notable_category_yoy_changes": [],
    }
    result = _fallback_findings(metrics)
    assert isinstance(result, InsightsOutput)
    banned_terms = ["fraud", "illegal", "guaranteed savings", "preferred supplier"]
    for finding in result.findings:
        text = (finding.title + " " + finding.description).lower()
        for term in banned_terms:
            assert term not in text
