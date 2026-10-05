"""Application context: settings, database, engines, job runner."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .config import Settings
from .db import Database
from .pipeline.asr import build_asr
from .pipeline.asr.mock import MockAsr
from .pipeline.correction import build_corrector
from .pipeline.correction.rules import RulesCorrector
from .pipeline.orchestrator import Engines
from .pipeline.pronunciation import build_pronunciation

log = logging.getLogger(__name__)


def build_engines(settings: Settings) -> tuple[Engines, list[str]]:
    """Build configured engines; fall back to offline ones (and say so) when unavailable."""
    notices: list[str] = []
    try:
        asr = build_asr(settings)
    except Exception as e:
        log.warning("ASR backend unavailable: %s", e)
        notices.append(f"ASR '{settings.asr_backend}' indisponible ({e}) : mode démo (mock).")
        asr = MockAsr()
    try:
        corrector = build_corrector(settings)
    except Exception as e:
        log.warning("Corrector unavailable: %s", e)
        notices.append(f"Correcteur '{settings.corrector_backend}' indisponible ({e}) : règles.")
        corrector = RulesCorrector()
    try:
        pron = build_pronunciation(settings)
    except Exception as e:
        log.warning("Pronunciation unavailable: %s", e)
        notices.append(f"Prononciation '{settings.pron_backend}' indisponible ({e}) : désactivée.")
        pron = None
    return Engines(asr=asr, corrector=corrector, pronunciation=pron), notices


@dataclass
class AppContext:
    settings: Settings
    db: Database
    engines: Engines
    notices: list[str] = field(default_factory=list)
    executor: ThreadPoolExecutor | None = None

    def __post_init__(self) -> None:
        if self.executor is None:
            self.executor = ThreadPoolExecutor(max_workers=self.settings.worker_threads,
                                               thread_name_prefix="dac-job")

    def recording_dir(self, rec_id: str):
        return self.settings.audio_dir / rec_id
