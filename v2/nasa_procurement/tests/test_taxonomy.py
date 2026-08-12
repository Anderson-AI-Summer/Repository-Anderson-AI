from src.taxonomy import (
    NEEDS_REVIEW_SUBCATEGORY,
    UNCLASSIFIED_CATEGORY,
    classify_deterministic,
    taxonomy_version,
    valid_categories,
    valid_subcategories,
    validate_classification,
)


def test_taxonomy_has_nine_top_level_categories():
    assert len(valid_categories()) == 9
    assert "Aerospace, Spacecraft, and Mission Systems" in valid_categories()
    assert UNCLASSIFIED_CATEGORY in valid_categories()


def test_every_category_has_at_least_one_subcategory():
    for cat in valid_categories():
        assert len(valid_subcategories(cat)) >= 1


def test_validate_classification_accepts_known_pair():
    assert validate_classification(UNCLASSIFIED_CATEGORY, NEEDS_REVIEW_SUBCATEGORY) is True


def test_validate_classification_rejects_unknown_category():
    assert validate_classification("Not A Real Category", "Whatever") is False


def test_validate_classification_rejects_mismatched_subcategory():
    assert validate_classification("Aerospace, Spacecraft, and Mission Systems", "Unclassified Spend") is False


def test_classify_deterministic_matches_psc_prefix():
    result = classify_deterministic("1810XX", None, None, None, None)
    assert result is not None
    category, subcategory, confidence, evidence = result
    assert category == "Aerospace, Spacecraft, and Mission Systems"
    assert subcategory == "Spacecraft & Satellite Systems"


def test_classify_deterministic_matches_naics_exact():
    result = classify_deterministic(None, None, "541715", "Research and Development", None)
    assert result is not None
    category, subcategory, confidence, evidence = result
    assert category == "Research, Engineering, and Technical Services"


def test_classify_deterministic_matches_keyword_fallback():
    result = classify_deterministic(None, None, None, None, "purchase of laboratory instrument for testing")
    assert result is not None
    category, subcategory, confidence, evidence = result
    assert category == "Scientific Instruments and Laboratory Supplies"


def test_classify_deterministic_returns_none_when_no_evidence_matches():
    result = classify_deterministic(None, None, None, None, "miscellaneous unspecified goods")
    assert result is None


def test_taxonomy_version_is_set():
    assert taxonomy_version()
