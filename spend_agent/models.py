"""Data structures shared across the spend agent pipeline."""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class Transaction:
    """A single normalized row from the raw transaction file."""

    row_id: int
    date: str
    vendor_raw: str
    description: str
    amount: float
    raw: Dict[str, str] = field(default_factory=dict)


@dataclass
class ClassifiedTransaction:
    """A transaction after vendor resolution, taxonomy classification, and supplier checks."""

    transaction: Transaction
    category: str
    canonical_vendor: str
    vendor_cluster_id: int
    vendor_alias_count: int
    preferred_supplier: Optional[str]
    bypassed_preferred_supplier: bool
