from dataclasses import replace
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from pydantic import ValidationError
import streamlit as st

from tt_automation.config import Settings
from tt_automation.excel.generator import (
    EXCEL_MIME_TYPE,
    GeneratedWorkbook,
    generate_workbook,
)
from tt_automation.excel.template_writer import TemplateWriteError
from tt_automation.extraction.documents import (
    SourceDocument,
    SUPPORTED_UPLOAD_TYPES,
)
from tt_automation.extraction.openai_extractor import (
    DocumentExtraction,
    ExtractionError,
    extract_each_document,
)
from tt_automation.extraction.workbook_reader import WorkbookReadError, workbook_to_text
from tt_automation.models import ApplicantDetails, TransferData


EXTRACTIONS_KEY = "document_extractions"
OUTPUTS_KEY = "generated_workbooks"
APPLICANT_KEY = "applicant_details"
SOURCE_SIGNATURE_KEY = "source_signature"
REVIEW_REVISION_KEY = "review_revision"

REQUIRED_FIELDS = {
    "beneficiary_name": "Beneficiary name",
    "currency": "Currency",
    "amount": "Amount",
    "beneficiary_account": "Beneficiary account",
    "beneficiary_address": "Beneficiary address",
    "beneficiary_bank": "Beneficiary bank",
    "beneficiary_bank_address": "Bank address / branch",
    "beneficiary_country": "Bank country",
    "swift_code": "SWIFT / BIC",
    "payment_purpose": "Payment purpose",
    "invoice_number": "Invoice number",
    "invoice_date": "Invoice date",
}


def main() -> None:
    st.set_page_config(
        page_title="TT Workbook",
        page_icon=":material/receipt_long:",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _apply_styles()
    settings = Settings()

    st.markdown(
        '<p class="eyebrow">INTERNATIONAL REMITTANCE</p>', unsafe_allow_html=True
    )
    st.title("TT Workbook")
    st.caption("Prepare the fixed telegraphic-transfer workbook from source documents.")

    _render_system_status(settings)
    st.divider()

    st.markdown(
        '<p class="step-label">01 &nbsp; SOURCE DOCUMENTS</p>', unsafe_allow_html=True
    )
    uploaded_files = st.file_uploader(
        "Invoice images or Excel files",
        type=SUPPORTED_UPLOAD_TYPES,
        accept_multiple_files=True,
        max_upload_size=20,
        help="Each file is extracted separately into its own workbook.",
    )
    documents = [
        SourceDocument(upload.name, upload.getvalue()) for upload in uploaded_files
    ]
    _sync_source_state(documents)
    summary_slot = st.empty()
    if not _has_extracted_data():
        with summary_slot.container():
            _render_source_summary(documents)

    can_extract = bool(documents) and settings.openai_api_key is not None
    if st.button(
        "Extract details",
        type="primary",
        icon=":material/document_scanner:",
        disabled=not can_extract,
    ):
        _extract(documents, settings)
        if _has_extracted_data():
            summary_slot.empty()

    if settings.openai_api_key is None:
        st.warning("Add `OPENAI_API_KEY` to `.env` before extracting documents.")

    extractions = st.session_state.get(EXTRACTIONS_KEY)
    if not extractions:
        return

    st.divider()
    st.markdown(
        '<p class="step-label">02 &nbsp; REVIEW DETAILS</p>', unsafe_allow_html=True
    )
    st.caption("Every source file has its own tab, review, and workbook.")
    tabs = st.tabs([_tab_label(index, item) for index, item in enumerate(extractions)])
    for index, (tab, extraction) in enumerate(zip(tabs, extractions)):
        with tab:
            _render_extraction(index, extraction)


def _tab_label(index: int, extraction: DocumentExtraction) -> str:
    name = extraction.document.name
    if len(name) > 28:
        name = f"{name[:25]}..."
    return f"{index + 1}. {name}{' (failed)' if extraction.error else ''}"


def _render_extraction(index: int, extraction: DocumentExtraction) -> None:
    if extraction.data is None:
        st.error(extraction.error or "This file could not be extracted.")
        return

    source_column, review_column = st.columns([1.1, 2], gap="large")
    with source_column:
        _render_source_preview([extraction.document])
    with review_column:
        _render_review_notes(extraction.data)
        _render_review_form(index, extraction)
    _render_download(index)


def _render_system_status(settings: Settings) -> None:
    first, second, third = st.columns(3)
    first.markdown(
        '<span class="status-dot status-ready"></span><strong>Template</strong><br>'
        '<span class="status-copy">Fixed TT workbook</span>',
        unsafe_allow_html=True,
    )
    api_status = (
        "Configured" if settings.openai_api_key is not None else "Missing .env key"
    )
    api_class = "status-ready" if settings.openai_api_key is not None else "status-warn"
    second.markdown(
        f'<span class="status-dot {api_class}"></span><strong>OpenAI</strong><br>'
        f'<span class="status-copy">{api_status}</span>',
        unsafe_allow_html=True,
    )
    third.markdown(
        f'<span class="status-dot status-ready"></span><strong>Model</strong><br>'
        f'<span class="status-copy">{settings.openai_model}</span>',
        unsafe_allow_html=True,
    )


def _has_extracted_data() -> bool:
    return bool(st.session_state.get(EXTRACTIONS_KEY))


def _render_source_summary(documents: list[SourceDocument]) -> None:
    if not documents:
        return

    image_documents = [document for document in documents if document.is_image]
    workbook_documents = [document for document in documents if document.is_workbook]

    st.caption(
        f"{len(documents)} source file{'s' if len(documents) != 1 else ''} selected"
    )
    if image_documents:
        preview_columns = st.columns(min(len(image_documents), 3))
        for index, document in enumerate(image_documents[:3]):
            preview_columns[index].image(
                document.content,
                caption=document.name,
                width=500,
            )
        if len(image_documents) > 3:
            st.caption(f"{len(image_documents) - 3} additional images selected")

    for document in workbook_documents:
        size = _format_file_size(len(document.content))
        st.markdown(
            f'<div class="file-row"><span class="file-icon">XLS</span>'
            f"<span><strong>{_escape_html(document.name)}</strong><br>"
            f"<small>{size}</small></span></div>",
            unsafe_allow_html=True,
        )


def _render_source_preview(documents: list[SourceDocument]) -> None:
    st.markdown("#### Source documents")
    if not documents:
        st.caption("Re-upload the source files to compare them with the values below.")
        return

    with st.container(height=900, border=False):
        for index, document in enumerate(documents):
            with st.expander(document.name, expanded=index == 0):
                if document.is_image:
                    st.image(document.content, width="stretch")
                    continue
                try:
                    st.code(workbook_to_text(document), language="text")
                except WorkbookReadError as error:
                    st.caption(str(error))


def _extract(documents: list[SourceDocument], settings: Settings) -> None:
    progress = st.progress(0.0, text=f"Extracting 0 of {len(documents)} files...")

    def report(completed: int, total: int) -> None:
        progress.progress(
            completed / total,
            text=f"Extracted {completed} of {total} files...",
        )

    try:
        with st.spinner(f"Extracting {len(documents)} file(s)...", show_time=True):
            extractions = extract_each_document(documents, settings, on_progress=report)
    except ExtractionError as error:
        st.error(str(error))
        return
    finally:
        progress.empty()

    st.session_state[EXTRACTIONS_KEY] = extractions
    st.session_state[OUTPUTS_KEY] = {}
    st.session_state[REVIEW_REVISION_KEY] = (
        st.session_state.get(REVIEW_REVISION_KEY, 0) + 1
    )

    failed = sum(1 for extraction in extractions if extraction.error)
    if failed:
        st.warning(
            f"{len(extractions) - failed} of {len(extractions)} files extracted. "
            "Open the tabs marked as failed for details."
        )
    else:
        st.success(
            f"{len(extractions)} file(s) extracted. "
            "Review each tab before generating its workbook."
        )


def _render_review_notes(data: TransferData) -> None:
    if data.review_notes:
        with st.expander("Items requiring attention", expanded=True):
            for note in data.review_notes:
                st.markdown(f"- {note}")


def _render_review_form(index: int, extraction: DocumentExtraction) -> None:
    data = extraction.data
    if data is None:
        return

    revision = st.session_state.get(REVIEW_REVISION_KEY, 0)
    stored_applicant = st.session_state.get(APPLICANT_KEY)
    applicant = (
        stored_applicant
        if isinstance(stored_applicant, ApplicantDetails)
        else ApplicantDetails()
    )

    def key(field: str) -> str:
        return f"review_{revision}_{index}_{field}"

    with st.form(f"transfer_review_{index}"):
        transfer_column, invoice_column = st.columns(2, gap="medium")
        with transfer_column:
            st.markdown("#### Transfer")
            transfer_date = st.date_input(
                "Transfer date",
                value=data.transfer_date or date.today(),
                format="DD/MM/YYYY",
                key=key("transfer_date"),
            )
            beneficiary_name = st.text_input(
                "Beneficiary name",
                value=data.beneficiary_name or "",
                key=key("beneficiary_name"),
            )
            beneficiary_account = st.text_input(
                "Beneficiary account",
                value=data.beneficiary_account or "",
                key=key("beneficiary_account"),
            )
            beneficiary_address = st.text_area(
                "Beneficiary address",
                value=data.beneficiary_address or "",
                key=key("beneficiary_address"),
            )
            currency_column, amount_column = st.columns(2)
            currency = currency_column.text_input(
                "Currency",
                value=data.currency or "",
                max_chars=3,
                key=key("currency"),
            )
            amount = amount_column.text_input(
                "Amount",
                value=_decimal_text(data.amount),
                key=key("amount"),
            )

        with invoice_column:
            st.markdown("#### Bank and invoice")
            beneficiary_bank = st.text_input(
                "Beneficiary bank",
                value=data.beneficiary_bank or "",
                key=key("beneficiary_bank"),
            )
            beneficiary_bank_address = st.text_area(
                "Bank address / branch",
                value=data.beneficiary_bank_address or "",
                key=key("beneficiary_bank_address"),
            )
            country_column, swift_column = st.columns(2)
            beneficiary_country = country_column.text_input(
                "Bank country",
                value=data.beneficiary_country or "",
                key=key("beneficiary_country"),
            )
            swift_code = swift_column.text_input(
                "SWIFT / BIC",
                value=data.swift_code or "",
                key=key("swift_code"),
            )
            payment_purpose = st.text_input(
                "Payment purpose",
                value=data.payment_purpose or "",
                key=key("payment_purpose"),
            )
            invoice_number = st.text_input(
                "Invoice number",
                value=data.invoice_number or "",
                key=key("invoice_number"),
            )
            invoice_date = st.date_input(
                "Invoice date",
                value=data.invoice_date,
                format="DD/MM/YYYY",
                key=key("invoice_date"),
            )

        with st.expander("Applicant and originator", expanded=False):
            st.caption(
                "Standing template values. Edit them before generating the workbook."
            )
            applicant_column, originator_column = st.columns(2, gap="medium")
            with applicant_column:
                applicant_name = st.text_input(
                    "Applicant's name",
                    value=applicant.applicant_name,
                    key=key("applicant_name"),
                )
                applicant_id_number = st.text_input(
                    "NRIC / passport no.",
                    value=applicant.applicant_id_number,
                    key=key("applicant_id_number"),
                )
                nationality_column, application_column = st.columns(2)
                nationality = nationality_column.text_input(
                    "Nationality",
                    value=applicant.nationality,
                    key=key("nationality"),
                )
                application_number = application_column.text_input(
                    "Application no.",
                    value=applicant.application_number,
                    key=key("application_number"),
                )
                contact_numbers = st.text_input(
                    "Tel. no. and fax no.",
                    value=applicant.contact_numbers,
                    key=key("contact_numbers"),
                )
                company_name = st.text_input(
                    "Company name",
                    value=applicant.company_name,
                    key=key("company_name"),
                )
                company_registration_number = st.text_input(
                    "Co. reg. no.",
                    value=applicant.company_registration_number,
                    key=key("company_registration_number"),
                )
                company_address = st.text_area(
                    "Company address",
                    value=applicant.company_address,
                    key=key("company_address"),
                )

            with originator_column:
                originator_name = st.text_input(
                    "Originator name",
                    value=applicant.originator_name,
                    key=key("originator_name"),
                )
                originator_id_number = st.text_input(
                    "Originator P.P no. / IC / ROC no.",
                    value=applicant.originator_id_number,
                    key=key("originator_id_number"),
                )
                originator_nationality_column, birth_date_column = st.columns(2)
                originator_nationality = originator_nationality_column.text_input(
                    "Originator nationality",
                    value=applicant.originator_nationality,
                    key=key("originator_nationality"),
                )
                originator_date_of_birth = birth_date_column.text_input(
                    "Date of birth",
                    value=applicant.originator_date_of_birth,
                    key=key("originator_date_of_birth"),
                )
                originator_place_of_birth = st.text_input(
                    "Place of birth",
                    value=applicant.originator_place_of_birth,
                    key=key("originator_place_of_birth"),
                )
                originator_address = st.text_area(
                    "Originator address",
                    value=applicant.originator_address,
                    key=key("originator_address"),
                )

        submitted = st.form_submit_button(
            "Generate workbook",
            type="primary",
            icon=":material/table_view:",
        )

    if not submitted:
        return

    try:
        reviewed_data = TransferData(
            transfer_date=transfer_date,
            beneficiary_name=_optional_text(beneficiary_name),
            currency=_optional_text(currency),
            amount=_optional_decimal(amount),
            beneficiary_account=_optional_text(beneficiary_account),
            beneficiary_address=_optional_text(beneficiary_address),
            beneficiary_bank=_optional_text(beneficiary_bank),
            beneficiary_bank_address=_optional_text(beneficiary_bank_address),
            beneficiary_country=_optional_text(beneficiary_country),
            swift_code=_optional_text(swift_code),
            payment_purpose=_optional_text(payment_purpose),
            invoice_number=_optional_text(invoice_number),
            invoice_date=invoice_date,
            review_notes=data.review_notes,
        )
        reviewed_applicant = ApplicantDetails(
            application_number=application_number,
            applicant_name=applicant_name,
            applicant_id_number=applicant_id_number,
            nationality=nationality,
            contact_numbers=contact_numbers,
            company_name=company_name,
            company_registration_number=company_registration_number,
            company_address=company_address,
            originator_name=originator_name,
            originator_nationality=originator_nationality,
            originator_id_number=originator_id_number,
            originator_date_of_birth=originator_date_of_birth,
            originator_place_of_birth=originator_place_of_birth,
            originator_address=originator_address,
        )
    except (ValidationError, InvalidOperation, ValueError) as error:
        st.error(f"Check the reviewed values: {error}")
        return

    st.session_state[APPLICANT_KEY] = reviewed_applicant

    if missing_fields := _missing_required_fields(reviewed_data):
        st.error(f"Complete these fields: {', '.join(missing_fields)}.")
        return

    try:
        with st.spinner("Creating the Excel workbook..."):
            generated = generate_workbook(reviewed_data, applicant=reviewed_applicant)
    except TemplateWriteError as error:
        st.error(str(error))
        return

    st.session_state[EXTRACTIONS_KEY][index] = replace(extraction, data=reviewed_data)
    st.session_state.setdefault(OUTPUTS_KEY, {})[index] = generated
    st.success("Workbook ready.")


def _render_download(index: int) -> None:
    generated = st.session_state.get(OUTPUTS_KEY, {}).get(index)
    if not isinstance(generated, GeneratedWorkbook):
        return

    st.divider()
    st.markdown('<p class="step-label">03 &nbsp; WORKBOOK</p>', unsafe_allow_html=True)
    st.download_button(
        "Download completed workbook",
        data=generated.content,
        file_name=generated.name,
        mime=EXCEL_MIME_TYPE,
        type="primary",
        icon=":material/download:",
        on_click="ignore",
        width="stretch",
        key=f"download_{index}",
    )


def _sync_source_state(documents: list[SourceDocument]) -> None:
    signature = _source_signature(documents)
    if st.session_state.get(SOURCE_SIGNATURE_KEY) == signature:
        return

    st.session_state[SOURCE_SIGNATURE_KEY] = signature
    st.session_state.pop(EXTRACTIONS_KEY, None)
    st.session_state.pop(OUTPUTS_KEY, None)


def _source_signature(documents: list[SourceDocument]) -> str:
    digest = sha256()
    for document in documents:
        digest.update(document.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(document.content)
        digest.update(b"\0")
    return digest.hexdigest()


def _missing_required_fields(data: TransferData) -> list[str]:
    return [
        label
        for field, label in REQUIRED_FIELDS.items()
        if getattr(data, field) in (None, "")
    ]


def _optional_text(value: str) -> str | None:
    stripped = value.strip()
    return stripped or None


def _optional_decimal(value: str) -> Decimal | None:
    stripped = value.strip().replace(",", "")
    return Decimal(stripped) if stripped else None


def _decimal_text(value: Decimal | None) -> str:
    return format(value, "f") if value is not None else ""


def _format_file_size(size: int) -> str:
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def _escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _apply_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --ink: #17252a;
            --muted: #617078;
            --paper: #f4f6f3;
            --line: #cfd8d3;
            --teal: #087f73;
            --coral: #c85d43;
        }
        .stApp {
            color: var(--ink);
            background-color: var(--paper);
            background-image:
                linear-gradient(rgba(23, 37, 42, 0.025) 1px, transparent 1px),
                linear-gradient(90deg, rgba(23, 37, 42, 0.025) 1px, transparent 1px);
            background-size: 24px 24px;
        }
        .block-container { max-width: 1600px; padding-top: 3rem; padding-bottom: 5rem; }
        h1, h2, h3, h4 { font-family: Georgia, "Times New Roman", serif; color: var(--ink); letter-spacing: 0; }
        h1 { font-size: 2.5rem; line-height: 1.05; margin-bottom: 0.4rem; }
        p, label, input, textarea, button { font-family: Aptos, "Segoe UI", sans-serif; letter-spacing: 0; }
        .eyebrow, .step-label {
            color: var(--coral);
            font-family: Aptos, "Segoe UI", sans-serif;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            margin: 0 0 0.45rem 0;
        }
        .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 8px; }
        .status-ready { background: var(--teal); }
        .status-warn { background: var(--coral); }
        .status-copy { color: var(--muted); font-size: 0.88rem; margin-left: 16px; }
        .file-row {
            align-items: center;
            background: rgba(255, 255, 255, 0.72);
            border-bottom: 1px solid var(--line);
            display: flex;
            gap: 0.8rem;
            padding: 0.75rem 0.2rem;
        }
        .file-icon {
            background: var(--ink);
            border-radius: 4px;
            color: white;
            font-size: 0.65rem;
            font-weight: 700;
            padding: 0.35rem 0.4rem;
        }
        div[data-testid="stFileUploaderDropzone"] {
            background: rgba(255, 255, 255, 0.78);
            border-color: #91a49b;
            border-radius: 6px;
        }
        div[data-testid="stForm"] { border: 0; padding: 0; }
        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea,
        div[data-testid="stDateInput"] input { border-radius: 4px; }
        .stButton button, .stDownloadButton button, .stFormSubmitButton button { border-radius: 4px; font-weight: 650; }
        hr { border-color: var(--line); margin: 2rem 0; }
        @media (max-width: 700px) {
            .block-container { padding: 1.5rem 1rem 3rem; }
            h1 { font-size: 2rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
