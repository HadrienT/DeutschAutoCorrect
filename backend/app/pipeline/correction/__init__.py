from __future__ import annotations

from ...config import Settings
from .base import Corrector


def build_corrector(settings: Settings) -> Corrector:
    if settings.corrector_backend == "anthropic":
        from .llm import AnthropicCorrector
        return AnthropicCorrector(settings.anthropic_model, settings.anthropic_effort)
    if settings.corrector_backend == "openai":
        from .llm import OpenAICompatCorrector
        return OpenAICompatCorrector(settings.llm_base_url, settings.llm_model,
                                     settings.llm_api_key, settings.llm_timeout,
                                     settings.llm_chunk)
    from .rules import RulesCorrector
    return RulesCorrector()
