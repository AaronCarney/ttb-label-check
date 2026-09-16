"""Orchestrator ABC + signature.

The class is `abc.ABC` (not Protocol) so subclass-or-error is enforced at
instantiation. Two concrete implementations: OpenAI, the default, and Anthropic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.application import Application
from app.schemas.extracted import FieldObservation
from app.schemas.refined import Refined
from app.schemas.rejection import ValidationResult


class Orchestrator(ABC):
    """The orchestrator seam. Two concrete impls: OpenAIStrict + AnthropicStrict."""

    @abstractmethod
    async def refine(
        self,
        application: Application,
        observations: list[FieldObservation],
        validation_results: list[ValidationResult],
    ) -> Refined:
        """Produce a Refined for one evaluation. The model never decides pass/fail."""
        ...

    @abstractmethod
    async def ensure_client(self) -> None:
        """Warm-up hook. OpenAI impl: no-op. Anthropic impl: import SDK + construct client."""
        ...
