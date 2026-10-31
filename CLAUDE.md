# CLAUDE.md — DeutschAutoCorrect

Automatic correction pipeline for spoken German exams (middle school). Read `docs/BLUEPRINT.md` (architecture, decisions) and `docs/WORK_PACKAGES.md` (breakdown) before any structural change.

## Commands

```bash
make install        # back end (pip -e .[dev]) + front end (npm ci)
make dev-back       # uvicorn app.main:app --reload  (http://localhost:8010 ; PORT=… to change)
make dev-front      # vite (http://localhost:5173, proxy /api → :8010)
make test           # pytest + vitest
make lint           # ruff + tsc
make demo           # runs the back end with mock engines and injects a demo recording
make up / down / logs   # docker compose: single image (front end + API + real engines), host network, port 8010
```
Back end: `cd backend && python -m pytest -q`. Front end: `cd frontend && npm test && npm run build`.

## Structure

```
backend/app/
  config.py db.py models.py main.py jobs.py
  api/            routes (recordings, rubrics, grading)
  pipeline/       audio.py asr/ segments.py pronunciation/ correction/ orchestrator.py merge.py
  scoring/        rubric.py engine.py
backend/tests/
frontend/src/     api/ components/ pages/ lib/ styles/
docs/
```

## Non-negotiable principles

1. **Faithful transcription**: never "clean" or correct the ASR text. The student's errors are the data. No grammatical `initial_prompt`, `condition_on_previous_text=False`.
2. **Interfaces + mocks**: every heavy stage (ASR, phonemes, LLM) is behind an interface (`Protocol`) with an offline implementation. Heavy imports (`faster_whisper`, `torch`, `transformers`) are **lazy** (inside the function/constructor), never at module level. Tests must never require a GPU, a model or the network.
3. **Grading = pure function** (`scoring/engine.py`): `(analysis, rubric, manual) -> Grade`. No I/O. Every rubric rule is added with a test.
4. **Non-student / non-German segments are not graded** (`graded=False`) but stay visible.
5. **The teacher has the last word**: every error can be confirmed, rejected or edited; `rejected` errors never count in the grade.
6. A failure of an *optional* stage (pronunciation, LLM) degrades the result (warning in `analysis.warnings`) but does not fail the job. An audio/ASR failure fails the job with a readable message.
7. Categories: `grammar|conjugation|vocabulary|pronunciation|text` (`text` = deviation from the reference text).
8. **Reference text** (recitation / reading): if it is set on the recording, the student's words are compared to this text (`pipeline/reference.py`, `text` errors, one per forgotten or replaced word) and the grammar corrector is not run.

## Conventions

- Python 3.11, typed, `ruff` (line-length 100). Pydantic v2 models. No ORM: `sqlite3` + `db.py`.
- LLM: `anthropic` SDK, default model `claude-opus-5-5`, **structured output** through `output_config.format` (JSON schema); **no forced `tool_choice`** (400 on this model), no `temperature`. Always validate/tolerate the received JSON.
- Local LLM: `openai` backend (`OpenAICompatCorrector`, httpx on `/v1/chat/completions`, `response_format` JSON schema, `temperature=0`); it checks the served model before each correction.
- Front end: React 18 + strict TypeScript, no UI library; CSS in `src/styles/` with variables (light/dark theme). Pure logic in `src/lib/` (tested with vitest).
- Rubric: grade = weighted mean of the criteria (`earned/max` × coefficient; default coefficient = max points, i.e. the simple sum). The `rhythm` criterion is a *suggestion* (long pauses, speech rate) that the teacher's input replaces.
- SQLite schema: any change goes through `Database._migrate` (`PRAGMA user_version`).
- Error identifiers are stable (`e_<hash>`), generated in `pipeline/merge.py`.
- **Language: English by default.** Everything you produce is in English: code, identifiers, comments, commit messages, PRs, issues, documentation and interface text. The only exception is the conversation: reply in the language the maintainer writes in, so in French when they write in French. The existing interface and error explanations are in French.
- Commits: short imperative messages; do not commit `data/`, `node_modules/`, `.env`.

## Environment variables

See `docs/BLUEPRINT.md` §2.6 and `.env.example`. Without configuration, the app starts in degraded mode (mock/rules); `GET /api/health` shows the active engines.

## Known traps

- Port 8000 is often taken by a local LLM server: the API is on 8010. `.env` is read at the repository root.
- Whisper's word timecodes are off by 150–300 ms: never cut the audio word by word for pronunciation (recognition per segment + `split_by_words`).
- The phoneme wav2vec2 tokenizer requires `phonemizer`: only the feature extractor and `vocab.json` are loaded (`ctc_decode`).
- `faster-whisper` hallucinates on silence: VAD is enabled, and segments with a high `no_speech_prob` are filtered.
- The phoneme wav2vec2 outputs espeak IPA: the comparator normalizes (length, diacritics) before aligning.
- Safari/iOS requires `Range` support for audio: do not remove the partial `StreamingResponse` from `/audio`.
