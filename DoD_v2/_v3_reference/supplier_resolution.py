"""Deterministic supplier-identity resolution.

Pipeline:
  1. Normalize punctuation/capitalization/suffixes/whitespace.
  2. Cluster by UEI (strong identity evidence), then by legacy DUNS, then by
     exact normalized name -- all high-confidence, no adjudication needed.
  3. Generate *candidate* fuzzy pairs across the remaining exact-name
     clusters (rapidfuzz + a whole-token-prefix safety rule, following the
     same false-merge lessons documented in v1/PROJECT_WRITEUP.md: matching
     on a shared leading token alone still merges unrelated companies, e.g.
     "First Interstate Bank" vs "First Republic Bank").
  4. Candidate pairs are adjudicated -- by the Supplier Resolution Agent when
     available, or a conservative deterministic fallback otherwise. Two
     clusters with conflicting non-null UEIs are NEVER merged, regardless of
     name similarity.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

SUFFIXES = (
    "INCORPORATED", "INC", "CORPORATION", "CORP", "COMPANY", "CO",
    "LIMITED LIABILITY COMPANY", "LLC", "LLP", "LP", "LTD", "LIMITED",
    "PLLC", "PC", "PA", "GROUP", "HOLDINGS", "ENTERPRISES",
)

_PUNCT_RE = re.compile(r"[.,\-&/\\()]")
_WS_RE = re.compile(r"\s+")


def normalize_name(raw: str) -> str:
    s = raw.upper()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    tokens = s.split(" ")
    while tokens and tokens[-1] in SUFFIXES:
        tokens.pop()
    return " ".join(tokens) if tokens else s


@dataclass
class SupplierCluster:
    cluster_id: str
    normalized_name: str
    raw_names: set[str] = field(default_factory=set)
    uei: str | None = None
    duns: str | None = None
    evidence: str = ""
    confidence: float = 0.0
    needs_review: bool = False
    canonical_name: str | None = None

    def display_name(self) -> str:
        if self.canonical_name:
            return self.canonical_name
        # Prefer the most common raw name; fall back to the normalized form.
        return max(self.raw_names, key=len) if self.raw_names else self.normalized_name


def _is_prefix_match(short: str, long: str) -> bool:
    """Whole-token prefix rule: the shorter name's tokens must be an exact
    leading-token prefix of the longer name's tokens (prevents "Staples" vs
    "Staples Business Advantage" false negatives while blocking "First
    Interstate Bank" vs "First Republic Bank" false positives)."""
    short_tokens = short.split(" ")
    long_tokens = long.split(" ")
    if len(short_tokens) >= len(long_tokens):
        return False
    return long_tokens[: len(short_tokens)] == short_tokens


def build_base_clusters(records: list[dict]) -> list[SupplierCluster]:
    """records: list of {"raw_name": str, "uei": str|None, "duns": str|None}.
    Groups by UEI first, then DUNS, then exact normalized name.
    """
    by_uei: dict[str, SupplierCluster] = {}
    by_duns: dict[str, SupplierCluster] = {}
    by_name: dict[str, SupplierCluster] = {}
    clusters: list[SupplierCluster] = []

    for rec in records:
        raw_name = rec["raw_name"]
        uei = rec.get("uei") or None
        duns = rec.get("duns") or None
        norm = normalize_name(raw_name)

        if uei and uei in by_uei:
            c = by_uei[uei]
        elif duns and duns in by_duns:
            c = by_duns[duns]
        elif not uei and not duns and norm in by_name:
            c = by_name[norm]
        else:
            c = SupplierCluster(cluster_id=f"cl_{len(clusters)}", normalized_name=norm)
            clusters.append(c)

        c.raw_names.add(raw_name)
        if uei:
            c.uei = uei
            by_uei[uei] = c
        if duns:
            c.duns = duns
            by_duns[duns] = c
        if not uei and not duns:
            by_name[norm] = c

    for c in clusters:
        if c.uei:
            c.confidence = 0.97
            c.evidence = f"Grouped by shared UEI {c.uei} across {len(c.raw_names)} raw name variant(s)"
        elif c.duns:
            c.confidence = 0.90
            c.evidence = f"Grouped by shared legacy DUNS {c.duns} across {len(c.raw_names)} raw name variant(s)"
        else:
            c.confidence = 0.75
            c.evidence = f"Exact normalized-name match ('{c.normalized_name}'), no UEI/DUNS evidence available"
    return clusters


@dataclass
class FuzzyCandidate:
    cluster_a: str
    cluster_b: str
    name_a: str
    name_b: str
    similarity: float
    prefix_rule_holds: bool


def generate_fuzzy_candidates(clusters: list[SupplierCluster], min_similarity: float = 82.0) -> list[FuzzyCandidate]:
    """Only pairs eligible: neither has a UEI, or both share the same UEI
    (already merged so wouldn't reach here); UEI conflicts are excluded
    outright."""
    candidates: list[FuzzyCandidate] = []
    unresolved = [c for c in clusters if not c.uei]
    for i, a in enumerate(unresolved):
        for b in unresolved[i + 1:]:
            if a.duns and b.duns and a.duns != b.duns:
                continue
            # partial_ratio (best-matching-substring score) rather than
            # token_sort_ratio: a true prefix relationship like "Staples" /
            # "Staples Business Advantage" scores ~100 under partial_ratio
            # but only ~40 under token_sort_ratio, which penalizes the
            # length difference too heavily to ever flag it as a candidate.
            score = fuzz.partial_ratio(a.normalized_name, b.normalized_name)
            if score < min_similarity:
                continue
            shorter, longer = sorted([a.normalized_name, b.normalized_name], key=len)
            prefix_ok = _is_prefix_match(shorter, longer)
            candidates.append(FuzzyCandidate(a.cluster_id, b.cluster_id, a.normalized_name, b.normalized_name, score, prefix_ok))
    return candidates


def adjudicate_fallback(candidate: FuzzyCandidate) -> tuple[bool, float, str]:
    """Conservative deterministic adjudication used when no LLM agent is
    available. Merges only when both the fuzzy score is high AND the
    whole-token-prefix rule holds; otherwise leaves unmerged and flags for
    review rather than guessing."""
    if candidate.prefix_rule_holds and candidate.similarity >= 90:
        return True, 0.65, (
            f"Deterministic fallback: '{candidate.name_a}' ~ '{candidate.name_b}' "
            f"(similarity={candidate.similarity:.0f}, whole-token prefix rule holds)"
        )
    return False, 0.4, (
        f"Ambiguous name variant '{candidate.name_a}' vs '{candidate.name_b}' "
        f"(similarity={candidate.similarity:.0f}) -- not merged, flagged for review"
    )
