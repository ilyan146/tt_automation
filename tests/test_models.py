from datetime import date

import pytest
from pydantic import ValidationError

from tt_automation.models import TransferData


@pytest.mark.parametrize(
    ("raw_date", "expected"),
    [
        ("JUL 3 2026", date(2026, 7, 3)),
        ("July 3, 2026", date(2026, 7, 3)),
        ("03/07/2026", date(2026, 7, 3)),
        ("2026-07-03", date(2026, 7, 3)),
    ],
)
def test_normalizes_document_dates(raw_date: str, expected: date) -> None:
    data = TransferData(invoice_date=raw_date)  # type: ignore[arg-type]

    assert data.invoice_date == expected


def test_rejects_unrecognized_document_date() -> None:
    with pytest.raises(ValidationError, match="recognizable invoice date"):
        TransferData(invoice_date="not a date")  # type: ignore[arg-type]
