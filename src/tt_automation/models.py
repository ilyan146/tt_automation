from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema, field_validator

MoneyAmount = Annotated[Decimal, WithJsonSchema({"type": "number"})]
"""Decimal that is advertised to the model as a plain JSON number.

Pydantic's default ``Decimal`` schema is an ``anyOf`` whose string branch carries a
regex with a negative lookahead. Constrained decoding cannot compile that pattern, so
the provider returns a 500 ``model_error``. Overriding the wire schema keeps full
``Decimal`` parsing and the ``ge`` constraint on the Python side.
"""


class TransferData(BaseModel):
    """Values extracted from source documents and written to the TT form."""

    model_config = ConfigDict(str_strip_whitespace=True)

    transfer_date: date | None = Field(
        default=None,
        description="Date on which the transfer application is prepared.",
    )
    beneficiary_name: str | None = Field(
        default=None,
        description="Full legal name of the payment beneficiary.",
    )
    currency: str | None = Field(
        default=None,
        description="Three-letter payment currency code, such as USD.",
    )
    amount: MoneyAmount | None = Field(
        default=None,
        ge=0,
        description="Total invoice or transfer amount, excluding the currency code.",
    )
    beneficiary_account: str | None = Field(
        default=None,
        description="Beneficiary bank account or IBAN, preserving leading zeroes.",
    )
    beneficiary_address: str | None = Field(
        default=None,
        description="Complete beneficiary address.",
    )
    beneficiary_bank: str | None = Field(
        default=None,
        description="Name of the beneficiary's bank.",
    )
    beneficiary_bank_address: str | None = Field(
        default=None,
        description="Branch name and full address of the beneficiary's bank.",
    )
    beneficiary_country: str | None = Field(
        default=None,
        description="Beneficiary bank country in uppercase English.",
    )
    swift_code: str | None = Field(
        default=None,
        description="Beneficiary bank SWIFT or BIC code.",
    )
    payment_purpose: str | None = Field(
        default=None,
        description="Short purpose beginning with 'Purchase of' when goods are invoiced.",
    )
    invoice_number: str | None = Field(
        default=None,
        description="Invoice number exactly as printed in the source.",
    )
    invoice_date: date | None = Field(
        default=None,
        description="Date printed on the invoice.",
    )
    review_notes: list[str] = Field(
        default_factory=list,
        description="Concise notes about ambiguous, conflicting, or unavailable values.",
    )

    @field_validator("transfer_date", "invoice_date", mode="before")
    @classmethod
    def parse_document_date(cls, value: Any) -> Any:
        if value in (None, "") or isinstance(value, date):
            return value

        if isinstance(value, str):
            normalized = " ".join(value.replace(",", " ").split())
            for date_format in (
                "%Y-%m-%d",
                "%b %d %Y",
                "%B %d %Y",
                "%d %b %Y",
                "%d %B %Y",
                "%d/%m/%Y",
            ):
                try:
                    return datetime.strptime(normalized, date_format).date()
                except ValueError:
                    continue

        raise ValueError("Date must be a recognizable invoice date")

    @field_validator("currency", "beneficiary_country", "swift_code")
    @classmethod
    def uppercase_codes(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class ApplicantDetails(BaseModel):
    """Standing applicant and originator values pre-filled in the TT form."""

    model_config = ConfigDict(str_strip_whitespace=True)

    application_number: str = "1"
    applicant_name: str = "Sharifa Jahan Binti Habibullah Khan"
    applicant_id_number: str = "791027-07-5568"
    nationality: str = "Malaysian"
    contact_numbers: str = "193708001"
    company_name: str = "Extra Cash SDN BHD"
    company_registration_number: str = "690908-V"
    company_address: str = (
        "Lot 1, Langkawi Fair Shopping Mall, Jalan Persiaran Putra, "
        "07000 Kuah, Langkawi, Kedah"
    )
    originator_name: str = "SSM"
    originator_nationality: str = ""
    originator_id_number: str = ""
    originator_date_of_birth: str = ""
    originator_place_of_birth: str = ""
    originator_address: str = "SSM"
