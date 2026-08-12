"""Vendor identity resolution.

Transaction files routinely refer to the same vendor by several raw strings
(store-number suffixes, legal-entity suffixes, ".com" variants, abbreviated
POS names). This module normalizes those raw names and clusters the ones
that plausibly refer to the same vendor, so downstream classification and
supplier checks operate on one canonical identity instead of N aliases.
"""

import json
from collections import defaultdict
from typing import Dict, Iterable, List, NamedTuple, Optional

_LEGAL_SUFFIXES = {
    "inc", "incorporated", "llc", "lc", "llp", "co", "corp", "corporation",
    "ltd", "limited", "company", "com",
}

_MIN_LEADING_TOKEN_LEN = 3


class VendorCluster(NamedTuple):
    cluster_id: int
    canonical_name: str
    aliases: List[str]


def load_vendor_aliases(path: str) -> Dict[str, str]:
    """Load a seed table of known abbreviations (e.g. "aws" -> "Amazon Web Services").

    Fuzzy string matching alone cannot bridge an abbreviation to a spelled-out
    name since they share almost no characters. Real vendor master data
    handles this with a maintained alias table; this is a small stand-in for
    that, keyed by the raw name lowercased and trimmed.
    """
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    return {k.strip().lower(): v for k, v in raw.items()}


def normalize_vendor(raw_name: str, aliases: Optional[Dict[str, str]] = None) -> str:
    """Strip punctuation, store/reference numbers, and legal suffixes for comparison."""
    if aliases:
        expanded = aliases.get(raw_name.strip().lower())
        if expanded:
            raw_name = expanded

    text = raw_name.upper()
    text = text.replace(".", " ").replace(",", " ").replace("-", " ").replace("/", " ")
    text = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text)
    tokens = text.split()

    cleaned_tokens = []
    for tok in tokens:
        # Drop pure store/reference numbers ("#1234", "04521") and legal
        # entity suffixes, which add noise without identifying the vendor.
        if tok.isdigit():
            continue
        if tok.lower() in _LEGAL_SUFFIXES:
            continue
        cleaned_tokens.append(tok)

    return " ".join(cleaned_tokens).strip()


def is_same_vendor(a: str, b: str) -> bool:
    """Decide whether two *normalized* vendor strings name the same vendor.

    Matching requires the shorter name to be a whole-token prefix of the
    longer one (e.g. "STAPLES" is a prefix of "STAPLES BUSINESS ADVANTAGE").
    Matching on the leading token alone is not enough: entire industries
    reuse the same first word across unrelated companies (many banks start
    with "First" or "Bank of"; many tech vendors end in "Technologies").
    Requiring every token of the shorter name to match, in order, from the
    start avoids merging e.g. "First Interstate Bank" with "First Republic
    Bank" while still merging "Staples" with "Staples Business Advantage".
    """
    if a == b:
        return True
    if not a or not b:
        return False

    tokens_a, tokens_b = a.split(), b.split()
    if not tokens_a or not tokens_b:
        return False

    shorter, longer = (tokens_a, tokens_b) if len(tokens_a) <= len(tokens_b) else (tokens_b, tokens_a)
    if len(shorter[0]) < _MIN_LEADING_TOKEN_LEN:
        return False

    return longer[: len(shorter)] == shorter


class _UnionFind:
    def __init__(self, items: Iterable[str]):
        self.parent = {item: item for item in items}

    def find(self, item: str) -> str:
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != root:
            self.parent[item], item = root, self.parent[item]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def build_vendor_registry(
    raw_names: Iterable[str], aliases: Optional[Dict[str, str]] = None
) -> "tuple[Dict[str, int], Dict[int, VendorCluster]]":
    """Cluster raw vendor name variants into canonical vendor identities.

    Returns:
        raw_to_cluster_id: maps each distinct raw vendor string to a cluster id.
        clusters: maps cluster id to a VendorCluster (canonical name + aliases).
    """
    counts: Dict[str, int] = defaultdict(int)
    for name in raw_names:
        counts[name] += 1
    unique_names = sorted(counts)

    normalized = {name: normalize_vendor(name, aliases) for name in unique_names}
    uf = _UnionFind(unique_names)

    for i in range(len(unique_names)):
        for j in range(i + 1, len(unique_names)):
            a, b = unique_names[i], unique_names[j]
            if is_same_vendor(normalized[a], normalized[b]):
                uf.union(a, b)

    groups: Dict[str, List[str]] = defaultdict(list)
    for name in unique_names:
        groups[uf.find(name)].append(name)

    raw_to_cluster_id: Dict[str, int] = {}
    clusters: Dict[int, VendorCluster] = {}
    for cluster_id, (_, members) in enumerate(sorted(groups.items()), start=1):
        # Canonical name = most frequently occurring raw variant; ties broken
        # toward shorter, non-domain-like, non-all-caps forms (e.g. "Staples
        # Inc" over "STAPLES.COM") since those read as the cleanest vendor name.
        canonical = sorted(
            members, key=lambda m: (-counts[m], "." in m, m.isupper(), len(m))
        )[0]
        clusters[cluster_id] = VendorCluster(
            cluster_id=cluster_id, canonical_name=canonical, aliases=sorted(members)
        )
        for member in members:
            raw_to_cluster_id[member] = cluster_id

    return raw_to_cluster_id, clusters
