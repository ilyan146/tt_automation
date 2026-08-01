from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from tt_automation.config import TEMPLATE_PATH
from tt_automation.excel.template_writer import fill_template
from tt_automation.models import TransferData


EXCEL_MIME_TYPE = "application/vnd.ms-excel"


@dataclass(frozen=True, slots=True)
class GeneratedWorkbook:
    name: str
    content: bytes


def generate_workbook(
    data: TransferData,
    template_path: Path = TEMPLATE_PATH,
) -> GeneratedWorkbook:
    """Populate the fixed template and return a download-ready workbook."""

    name = output_filename(data)
    with TemporaryDirectory(prefix="tt-automation-") as temporary_directory:
        output_path = Path(temporary_directory) / name
        fill_template(template_path, output_path, data)
        content = output_path.read_bytes()
    return GeneratedWorkbook(name=name, content=content)


def output_filename(data: TransferData) -> str:
    identifier = _safe_filename_part(data.invoice_number or "transfer")
    beneficiary = _safe_filename_part(data.beneficiary_name or "beneficiary")
    document_date = data.invoice_date or date.today()
    return f"{identifier}_{beneficiary}_{document_date.isoformat()}.xls"


def _safe_filename_part(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
    return normalized.strip("_")[:50] or "document"
