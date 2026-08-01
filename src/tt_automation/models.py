from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    amount: Decimal | None = Field(
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
