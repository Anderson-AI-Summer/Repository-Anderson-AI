from src.supplier_resolution import (
    adjudicate_fallback,
    build_base_clusters,
    generate_fuzzy_candidates,
    normalize_name,
)


def test_normalize_name_strips_suffix_and_punctuation():
    assert normalize_name("Acme, Inc.") == "ACME"
    assert normalize_name("Staples Business Advantage, LLC") == "STAPLES BUSINESS ADVANTAGE"


def test_normalize_name_collapses_whitespace():
    assert normalize_name("  Acme   Corp  ") == "ACME"


def test_clustering_groups_by_shared_uei():
    records = [
        {"raw_name": "Acme Inc.", "uei": "UEI1", "duns": None},
        {"raw_name": "ACME INCORPORATED", "uei": "UEI1", "duns": None},
    ]
    clusters = build_base_clusters(records)
    assert len(clusters) == 1
    assert clusters[0].confidence > 0.9


def test_conflicting_ueis_are_never_merged_even_with_identical_names():
    records = [
        {"raw_name": "Acme Inc.", "uei": "UEI1", "duns": None},
        {"raw_name": "Acme Inc.", "uei": "UEI2", "duns": None},
    ]
    clusters = build_base_clusters(records)
    assert len(clusters) == 2
    candidates = generate_fuzzy_candidates(clusters)
    # Both clusters have a UEI, so they are excluded from fuzzy candidate generation
    # entirely -- never merged on name similarity alone.
    assert candidates == []


def test_fallback_adjudication_blocks_shared_leading_word_false_merge():
    # "First Interstate Bank" vs "First Republic Bank": same leading token,
    # but the shorter name is not a whole-token prefix of the longer one.
    records = [
        {"raw_name": "First Interstate Bank", "uei": None, "duns": None},
        {"raw_name": "First Republic Bank", "uei": None, "duns": None},
    ]
    clusters = build_base_clusters(records)
    candidates = generate_fuzzy_candidates(clusters, min_similarity=0)
    assert len(candidates) == 1
    merge, confidence, evidence = adjudicate_fallback(candidates[0])
    assert merge is False


def test_fallback_adjudication_merges_true_prefix_variant():
    records = [
        {"raw_name": "Staples", "uei": None, "duns": None},
        {"raw_name": "Staples Business Advantage", "uei": None, "duns": None},
    ]
    clusters = build_base_clusters(records)
    candidates = generate_fuzzy_candidates(clusters, min_similarity=0)
    assert len(candidates) == 1
    merge, confidence, evidence = adjudicate_fallback(candidates[0])
    assert merge is True
    assert confidence < 0.7  # never as confident as a UEI-backed match
