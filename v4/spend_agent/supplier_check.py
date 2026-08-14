"""Preferred-supplier ("maverick spend") checks.

A category with a designated preferred supplier should see spend routed to
that supplier's canonical vendor identity. Anything else in that category
is flagged as having bypassed the preferred supplier.
"""

from typing import Dict, Optional, Tuple

from spend_agent.vendor_resolution import normalize_vendor, is_same_vendor


def check_preferred_supplier(
    category: str,
    canonical_vendor: str,
    preferred_suppliers: Dict[str, str],
    aliases: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[str], bool]:
    """Return (preferred_supplier_name_or_None, bypassed).

    Categories with no configured preferred supplier are never flagged.
    """
    preferred = preferred_suppliers.get(category)
    if preferred is None:
        return None, False

    bypassed = not is_same_vendor(
        normalize_vendor(canonical_vendor, aliases), normalize_vendor(preferred, aliases)
    )
    return preferred, bypassed
