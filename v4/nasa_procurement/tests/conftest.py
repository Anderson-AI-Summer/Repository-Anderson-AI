import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from src.schema import CleanTransaction


def make_clean_transaction(**overrides) -> CleanTransaction:
    defaults = dict(
        transaction_id="t1",
        award_id_piid="AWD001",
        action_date=dt.date(2020, 1, 15),
        fiscal_year=2020,
        transaction_obligated_amount=1000.0,
        recipient_name_raw="ACME CORP",
        recipient_uei="UEI000001",
        psc_code="AC13",
        naics_code="541715",
        transaction_description="research services",
        award_detail_available=True,
    )
    defaults.update(overrides)
    return CleanTransaction(**defaults)


@pytest.fixture
def make_txn():
    return make_clean_transaction
