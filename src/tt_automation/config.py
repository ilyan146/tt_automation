from pathlib import Path
from typing import Any, Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = PROJECT_ROOT / "templates" / "telegraphic_transfer_template.xls"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5"
    openai_reasoning_effort: Literal["low", "medium", "high"] = "low"
    openai_timeout_seconds: float = 90.0
    openai_base_url: str
    openai_max_retries: int = 2

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def blank_api_key_is_missing(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value
