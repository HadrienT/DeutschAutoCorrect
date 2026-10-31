"""Runtime configuration (env vars prefixed DAC_)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # The repo-root .env is found whatever the working directory (make runs from backend/).
    model_config = SettingsConfigDict(env_prefix="DAC_", env_file=(ROOT / ".env", ".env"),
                                      extra="ignore")

    data_dir: Path = Path("./data")
    asr_backend: str = "mock"  # faster-whisper | mock
    whisper_model: str = "large-v3"
    whisper_device: str = "auto"
    whisper_device_index: int = 0  # GPU to use when several are present
    whisper_compute_type: str = "default"
    pron_backend: str = "none"  # wav2vec2 | mock | none
    phoneme_model: str = "facebook/wav2vec2-xlsr-53-espeak-cv-ft"
    phoneme_device: str = "auto"  # auto | cpu | cuda | cuda:N
    corrector_backend: str = "rules"  # anthropic | openai (OpenAI-compatible server) | rules
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: str = "medium"
    llm_base_url: str = "http://127.0.0.1:8000/v1"  # openai backend (llama.cpp, vLLM, Ollama...)
    llm_model: str = ""  # empty = whatever the server serves
    llm_api_key: str = ""
    llm_timeout: float = 300.0
    llm_chunk: int = 4  # segments per request
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
