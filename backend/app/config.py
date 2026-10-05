"""Runtime configuration (env vars prefixed DAC_)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DAC_", env_file=".env", extra="ignore")

    data_dir: Path = Path("./data")
    asr_backend: str = "mock"  # faster-whisper | mock
    whisper_model: str = "large-v3"
    whisper_device: str = "auto"
    whisper_compute_type: str = "default"
    pron_backend: str = "none"  # wav2vec2 | mock | none
    phoneme_model: str = "facebook/wav2vec2-xlsr-53-espeak-cv-ft"
    corrector_backend: str = "rules"  # anthropic | rules
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: str = "medium"
    max_upload_mb: int = 300
    worker_threads: int = 2
    cors_origins: str = "http://localhost:5173"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "dac.sqlite3"


@lru_cache
def get_settings() -> Settings:
    return Settings()
