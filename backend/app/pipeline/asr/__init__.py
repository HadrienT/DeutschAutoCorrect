from __future__ import annotations

from ...config import Settings
from .base import AsrEngine


def build_asr(settings: Settings) -> AsrEngine:
    if settings.asr_backend == "faster-whisper":
        from .faster_whisper import FasterWhisperAsr
        return FasterWhisperAsr(settings.whisper_model, settings.whisper_device,
                                settings.whisper_compute_type)
    from .mock import MockAsr
    return MockAsr()
