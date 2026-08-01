from contextlib import suppress
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
import shutil
from typing import TypeAlias

import xlwings as xw

from tt_automation.models import ApplicantDetails, TransferData


TEMPLATE_SHEET = "Sheet1 (2)"
CellValue: TypeAlias = str | datetime

APPLICANT_CELLS: dict[str, str] = {
    "L3": "application_number",
    "E10": "applicant_name",
    "L10": "applicant_id_number",
    "E11": "nationality",
    "L11": "contact_numbers",
    "E12": "company_name",
    "K12": "company_address",
    "E13": "company_registration_number",
    "K15": "originator_date_of_birth",
    "C16": "originator_name",
    "K16": "originator_place_of_birth",
    "D17": "originator_nationality",
    "K17": "originator_address",
    "E18": "originator_id_number",
}


class TemplateWriteError(RuntimeError):
    """Raised when the fixed Excel template cannot be populated."""


def build_cell_values(
    data: TransferData,
    applicant: ApplicantDetails | None = None,
) -> dict[str, CellValue]:
    """Map reviewed transfer data to the fixed template's destination cells."""

    details = applicant or ApplicantDetails()
    values: dict[str, CellValue] = {
        address: getattr(details, field) for address, field in APPLICANT_CELLS.items()
    }
    values.update(
        {
            "L7": _excel_date(data.transfer_date),
            "E21": data.beneficiary_name or "",
            "K21": _format_currency_amount(data.currency, data.amount),
            "B25": f"Beneficiary's A/c No.. {data.beneficiary_account or ''}",
            "E28": data.beneficiary_address or "",
            "E30": data.beneficiary_bank or "",
            "L30": data.beneficiary_country or "",
            "L32": data.swift_code or "",
            "B33": data.beneficiary_bank_address or "",
            "D41": data.payment_purpose or "",
            "D42": data.invoice_number or "",
            "D43": _excel_date(data.invoice_date),
        }
    )
    return values


def fill_template(
    template_path: Path,
    output_path: Path,
    data: TransferData,
    applicant: ApplicantDetails | None = None,
) -> None:
    """Copy and populate the legacy workbook while preserving its formatting."""

    if not template_path.is_file():
        raise TemplateWriteError(f"Template not found: {template_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_path, output_path)
    _write_cells(output_path, build_cell_values(data, applicant))


def _write_cells(workbook_path: Path, values: dict[str, CellValue]) -> None:
    app = None
    workbook = None

    try:
        app = xw.App(visible=False, add_book=False)
        app.display_alerts = False
        app.screen_updating = False
        workbook = app.books.open(
            str(workbook_path.resolve()),
            update_links=False,
            read_only=False,
        )
        worksheet = workbook.sheets[TEMPLATE_SHEET]

        for address, value in values.items():
            cell = worksheet.range(address)
            cell.value = value
            if address in {"L7", "D43"}:
                cell.number_format = "dd/mm/yyyy"

        workbook.save()
    except Exception as error:
        raise TemplateWriteError(
            "Excel could not create the completed transfer workbook."
        ) from error
    finally:
        if workbook is not None:
            with suppress(Exception):
                workbook.close()
        if app is not None:
            with suppress(Exception):
                app.kill()


def _excel_date(value: date | None) -> datetime | str:
    return datetime.combine(value, time.min) if value else ""


def _format_currency_amount(
    currency: str | None,
    amount: Decimal | None,
) -> str:
    if amount is None:
        return currency or ""
    formatted_amount = f"{amount:,.2f}"
    return f"{currency} {formatted_amount}" if currency else formatted_amount
