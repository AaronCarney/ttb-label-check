"""Pydantic Settings — single source of truth for the env-var inventory.

Every secret name is read here and **only** here. The grep
enforcement test (``tests/test_secrets_grep.py``) asserts no other module
references ``os.environ`` directly.
"""

from __future__ import annotations

from importlib import metadata
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

    # How long one whole evaluation may run before the engine stops it. This is
    # a runaway guard — an evaluation that has gone wrong should not hold a
    # request open — and it is deliberately NOT the five seconds R15/NFR-1
    # measures. It used to be, and the consequence was that a check running
    # slightly over the requirement was truncated rather than merely slow,
    # which fails the requirement's own words ("show their results within 5
    # seconds") on top of failing FR-1 and FR-8.
    #
    # 30 seconds: six times the slowest whole check measured on the live
    # service (5.04 s on 2026-09-17), so no legitimate check can reach it, and
    # far short of Cloud Run's 900 s request timeout (`scripts/deploy.sh`),
    # which is the outer bound but is far too long for a page a person is
    # waiting at. `tests/test_deploy_healthz.py` independently picked the same
    # 30 s as the point past which a check has not finished at all.
    evaluation_guard_seconds: float = Field(default=30.0, gt=0, alias="EVALUATION_GUARD_SECONDS")

    # How many CPU threads the local OCR reader is allowed. The default is the
    # deploy target's core count — the Cloud Run service is 4 vCPU (decision
    # 0025) — so a developer's machine reads a label the way the deployed
    # product does instead of taking every core it can find.
    ocr_num_threads: int = Field(default=4, ge=1, alias="OCR_NUM_THREADS")

    # Dev-only routes. Empty string and unset both coerce to False.
    dev_mode: bool = Field(default=False, alias="DEV_MODE")

    # Future OTel collector endpoint.
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )

    # The commit this process is running, stamped by the deploy
    # (`scripts/deploy.sh`). Unset outside a deploy — a working tree is not a
    # commit — and `/api/health` reports "unknown" rather than omitting it, so a
    # deploy that failed to stamp itself is distinguishable from an older build
    # of the app that never could.
    git_commit: str | None = Field(default=None, alias="GIT_COMMIT")

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
    def from_env(cls) -> Settings:
        """Convenience factory; equivalent to ``cls()``."""
        return cls()

    @property
    def app_version(self) -> str:
        """The version actually running, read from the installed package.

        It was a hardcoded "0.1.0" here, which `/api/health` reports and which
        is the only thing telling anyone which build is live. A constant cannot
        be that: it went on saying 0.1.0 after the release that cut 0.2.0, so
        the one field a reviewer would trust to identify the deploy was wrong.
        Read from the package metadata the image installs, so it is the running
        build's own number and not a claim about it.

        Where the metadata is missing the answer is "unknown", not a guess: a
        version this cannot establish is one it must not state.
        """
        try:
            return metadata.version("ttb-label-prototype")
        except metadata.PackageNotFoundError:
            return "unknown"
