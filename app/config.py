"""Pydantic Settings — single source of truth for the env-var inventory.

Every secret name is read here and **only** here. The grep
enforcement test (``tests/test_secrets_grep.py``) asserts no other module
references ``os.environ`` directly.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_TRUTHY = frozenset({"1", "true", "yes", "on"})


class Settings(BaseSettings):
    """Process-level configuration loaded from environment variables.

    The complete env-var inventory for the app.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # Which reader turns a label image into fields (decision 0005). `local`
    # runs a CPU OCR engine inside this process and is the default, so a clone
    # checks labels with no key and no outbound call. `cloud` calls a hosted
    # vision model, reads more accurately, and needs OPENAI_API_KEY.
    vision_mode: Literal["local", "cloud"] = Field(default="local", alias="VISION_MODE")

    # Secret — required only when VISION_MODE=cloud selects the hosted reader.
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")

    # Pinned model + prompt versions for the cloud reader. Pinning keeps its
    # readings reproducible across runs.
    llm_model_snapshot: str = Field(default="gpt-4o-2024-08-06", alias="LLM_MODEL_SNAPSHOT")
    prompt_version: str = Field(default="v1", alias="PROMPT_VERSION")

    # Batch lookahead window.
    lookahead_k: int = Field(default=3, ge=1, alias="LOOKAHEAD_K")

    # Dev-only routes. Empty string and unset both coerce to False.
    dev_mode: bool = Field(default=False, alias="DEV_MODE")

    # Future OTel collector endpoint.
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )

    # Logging level.
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # YAML rules directory.
    rules_root: Path = Field(
        default=Path("rules").resolve(),
        alias="RULES_ROOT",
        description="Absolute path to the YAML rules directory.",
    )

    @field_validator("dev_mode", mode="before")
    @classmethod
    def _coerce_dev_mode(cls, value: object) -> bool:
        """Empty string / None / falsy strings → False; truthy strings → True."""
        if value is None or value == "":
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in _TRUTHY
        return bool(value)

    @classmethod
    def from_env(cls) -> "Settings":
        """Convenience factory; equivalent to ``cls()``."""
        return cls()

    @property
    def app_version(self) -> str:
        return "0.1.0"
