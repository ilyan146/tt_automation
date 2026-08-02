from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class DocumentKind(StrEnum):
    """How a source document is presented to the model."""

    IMAGE = "image"
    PDF = "pdf"
    WORKBOOK = "workbook"


SUFFIX_KINDS: dict[str, DocumentKind] = {
    ".jpeg": DocumentKind.IMAGE,
    ".jpg": DocumentKind.IMAGE,
    ".png": DocumentKind.IMAGE,
    ".webp": DocumentKind.IMAGE,
    ".pdf": DocumentKind.PDF,
    ".xls": DocumentKind.WORKBOOK,
    ".xlsm": DocumentKind.WORKBOOK,
    ".xlsx": DocumentKind.WORKBOOK,
}
"""Every accepted suffix and the extraction strategy it maps to."""

MEDIA_TYPES: dict[str, str] = {
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}
"""Media types for the suffixes sent to OpenAI as base64 data URLs."""

MAGIC_PREFIXES: dict[str, bytes] = {".pdf": b"%PDF-"}
"""Leading bytes a suffix must carry before its content is worth uploading."""

SUPPORTED_SUFFIXES = frozenset(SUFFIX_KINDS)
SUPPORTED_UPLOAD_TYPES = tuple(
    suffix.removeprefix(".") for suffix in sorted(SUPPORTED_SUFFIXES)
)
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024


class InvalidDocumentError(ValueError):
    """Raised when an uploaded document is empty, too large, or unsupported."""


@dataclass(frozen=True, slots=True)
class SourceDocument:
    name: str
    content: bytes

    @property
    def suffix(self) -> str:
        return Path(self.name).suffix.lower()

    @property
    def kind(self) -> DocumentKind:
        try:
            return SUFFIX_KINDS[self.suffix]
        except KeyError as error:
            raise InvalidDocumentError(f"Unsupported file type: {self.name}") from error

    @property
    def media_type(self) -> str:
        try:
            return MEDIA_TYPES[self.suffix]
        except KeyError as error:
            raise InvalidDocumentError(
                f"{self.name} cannot be sent as a data URL."
            ) from error

    def validate(self) -> None:
        if self.suffix not in SUPPORTED_SUFFIXES:
            raise InvalidDocumentError(f"Unsupported file type: {self.name}")
        if not self.content:
            raise InvalidDocumentError(f"File is empty: {self.name}")
        if len(self.content) > MAX_DOCUMENT_BYTES:
            raise InvalidDocumentError(
                f"{self.name} exceeds the {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB limit."
            )
        expected_prefix = MAGIC_PREFIXES.get(self.suffix)
        if expected_prefix and not self.content.startswith(expected_prefix):
            raise InvalidDocumentError(f"{self.name} is not a readable {self.kind}.")
