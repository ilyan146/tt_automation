from contextlib import suppress
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
import shutil
from typing import TypeAlias

import xlwings as xw

from tt_automation.models import TransferData


TEMPLATE_SHEET = "Sheet1 (2)"
CellValue: TypeAlias = str | datetime


class TemplateWriteError(RuntimeError):
    """Raised when the fixed Excel template cannot be populated."""


def build_cell_values(data: TransferData) -> dict[str, CellValue]:
    """Map reviewed transfer data to the fixed template's destination cells."""

    return {
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


def fill_template(
    template_path: Path,
    output_path: Path,
    data: TransferData,
) -> None:
    """Copy and populate the legacy workbook while preserving its formatting."""

    if not template_path.is_file():
        raise TemplateWriteError(f"Template not found: {template_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_path, output_path)
    _write_cells(output_path, build_cell_values(data))


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
