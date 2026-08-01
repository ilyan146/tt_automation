from dataclasses import dataclass
from pathlib import Path


IMAGE_MEDIA_TYPES = {
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
WORKBOOK_SUFFIXES = frozenset({".xls", ".xlsx", ".xlsm"})
SUPPORTED_SUFFIXES = frozenset(IMAGE_MEDIA_TYPES) | WORKBOOK_SUFFIXES
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
    def is_image(self) -> bool:
        return self.suffix in IMAGE_MEDIA_TYPES

    @property
    def is_workbook(self) -> bool:
        return self.suffix in WORKBOOK_SUFFIXES

    @property
    def image_media_type(self) -> str:
        try:
            return IMAGE_MEDIA_TYPES[self.suffix]
        except KeyError as error:
            raise InvalidDocumentError(
                f"{self.name} is not a supported image."
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
