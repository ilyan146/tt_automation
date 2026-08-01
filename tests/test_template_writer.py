from datetime import date
from decimal import Decimal
from pathlib import Path
import sys

import pytest
import xlrd

from tt_automation.config import TEMPLATE_PATH
from tt_automation.excel.template_writer import build_cell_values, fill_template
from tt_automation.models import TransferData


SAMPLE_DATA = TransferData(
    transfer_date=date(2026, 8, 1),
    beneficiary_name="Example Beneficiary Ltd",
    currency="usd",
    amount=Decimal("1234.50"),
    beneficiary_account="0012345",
    beneficiary_address="1 Example Road, Nanchang, China",
    beneficiary_bank="Bank of China",
    beneficiary_bank_address="Jiangxi Branch, Nanchang, China",
    beneficiary_country="China",
    swift_code="bkchcnbj550",
    payment_purpose="Purchase of glassine paper",
    invoice_number="INV-42",
    invoice_date=date(2026, 7, 3),
)


def test_build_cell_values_matches_fixed_template() -> None:
    values = build_cell_values(SAMPLE_DATA)

    assert values["E21"] == "Example Beneficiary Ltd"
    assert values["K21"] == "USD 1,234.50"
    assert values["B25"] == "Beneficiary's A/c No.. 0012345"
    assert values["D42"] == "INV-42"


@pytest.mark.skipif(sys.platform != "win32", reason="Excel COM requires Windows")
def test_fill_template_preserves_xls_and_writes_values(tmp_path: Path) -> None:
    output_path = tmp_path / "completed.xls"

    fill_template(TEMPLATE_PATH, output_path, SAMPLE_DATA)

    workbook = xlrd.open_workbook(output_path)
    sheet = workbook.sheet_by_name("Sheet1 (2)")
    assert sheet.cell_value(20, 4) == "Example Beneficiary Ltd"
    assert sheet.cell_value(20, 10) == "USD 1,234.50"
    assert sheet.cell_value(24, 1) == "Beneficiary's A/c No.. 0012345"
    assert sheet.cell_value(41, 3) == "INV-42"
