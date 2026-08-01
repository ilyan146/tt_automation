from datetime import date

from tt_automation.excel.generator import output_filename
from tt_automation.models import TransferData


def test_output_filename_is_stable_and_windows_safe() -> None:
    data = TransferData(
        invoice_number="INV/42:2026",
        beneficiary_name="Example & Sons Co., Ltd",
        invoice_date=date(2026, 7, 3),
    )

    assert output_filename(data) == (
        "INV_42_2026_Example_Sons_Co_Ltd_2026-07-03.xls"
    )
