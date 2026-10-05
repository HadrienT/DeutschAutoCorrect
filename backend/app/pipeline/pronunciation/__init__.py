from __future__ import annotations

from ...config import Settings
from .base import PronunciationEngine


def build_pronunciation(settings: Settings) -> PronunciationEngine | None:
    if settings.pron_backend == "wav2vec2":
        from .wav2vec2 import Wav2Vec2Phonemes
        return Wav2Vec2Phonemes(settings.phoneme_model, settings.whisper_device)
    if settings.pron_backend == "mock":
        from .mock import MockPronunciation
        return MockPronunciation()
    return None
