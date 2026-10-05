from __future__ import annotations

from ...config import Settings
from .base import Corrector


def build_corrector(settings: Settings) -> Corrector:
    if settings.corrector_backend == "anthropic":
        from .llm import AnthropicCorrector
        return AnthropicCorrector(settings.anthropic_model, settings.anthropic_effort)
    from .rules import RulesCorrector
    return RulesCorrector()
