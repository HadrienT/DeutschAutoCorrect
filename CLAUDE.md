# CLAUDE.md — DeutschAutoCorrect

Pipeline de correction automatique d'oraux d'allemand (collège). Lire `docs/BLUEPRINT.md` (architecture, décisions) et `docs/WORK_PACKAGES.md` (découpage) avant toute modification structurelle.

## Commandes

```bash
make install        # back (pip -e .[dev]) + front (npm ci)
make dev-back       # uvicorn app.main:app --reload  (http://localhost:8000)
make dev-front      # vite (http://localhost:5173, proxy /api → :8000)
make test           # pytest + vitest
make lint           # ruff + tsc
make demo           # lance le back avec moteurs mock et injecte un enregistrement de démo
```
Back : `cd backend && python -m pytest -q`. Front : `cd frontend && npm test && npm run build`.

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

## Principes non négociables

1. **Transcription fidèle** : ne jamais « nettoyer » ni corriger le texte ASR. Les erreurs de l'élève sont la donnée. Pas d'`initial_prompt` grammatical, `condition_on_previous_text=False`.
2. **Interfaces + mocks** : toute étape lourde (ASR, phonèmes, LLM) est derrière une interface (`Protocol`) avec une implémentation hors-ligne. Les imports lourds (`faster_whisper`, `torch`, `transformers`) sont **paresseux** (dans la fonction/constructeur), jamais au niveau module. Les tests ne doivent jamais nécessiter GPU, modèle ou réseau.
3. **Notation = fonction pure** (`scoring/engine.py`) : `(analysis, rubric, manual) -> Grade`. Aucun I/O. Toute règle de barème s'ajoute avec un test.
4. **Les segments non-élève / non-allemands ne sont pas notés** (`graded=False`) mais restent visibles.
5. **L'enseignant a le dernier mot** : toute erreur est confirmable/rejetable/modifiable ; les erreurs `rejected` ne comptent jamais dans la note.
6. Un échec d'étape *optionnelle* (prononciation, LLM) dégrade le résultat (avertissement dans `analysis.warnings`) mais ne fait pas échouer le job. Un échec audio/ASR fait échouer le job avec un message lisible.
7. Textes d'interface et explications d'erreurs **en français** ; code, identifiants, commentaires en anglais ; catégories : `grammar|conjugation|vocabulary|pronunciation`.

## Conventions

- Python 3.11, typé, `ruff` (line-length 100). Modèles pydantic v2. Pas d'ORM : `sqlite3` + `db.py`.
- LLM : SDK `anthropic`, modèle par défaut `claude-opus-5-5`, **sortie structurée** via `output_config.format` (JSON schema) ; **pas de `tool_choice` forcé** (400 sur ce modèle), pas de `temperature`. Toujours valider/tolérer le JSON reçu.
- Front : React 18 + TypeScript strict, pas de librairie UI ; CSS dans `src/styles/` avec variables (thème clair/sombre). Logique pure dans `src/lib/` (testée avec vitest).
- Les identifiants d'erreur sont stables (`e_<hash>`), générés dans `pipeline/merge.py`.
- Commits : messages courts à l'impératif ; ne pas commiter `data/`, `node_modules/`, `.env`.

## Variables d'environnement

Voir `docs/BLUEPRINT.md` §2.6 et `.env.example`. Sans configuration, l'appli démarre en mode dégradé (mock/règles) — `GET /api/health` indique les moteurs actifs.

## Pièges connus

- `faster-whisper` hallucine sur les silences : le VAD est activé, et les segments à `no_speech_prob` élevé sont filtrés.
- Le wav2vec2 de phonèmes sort de l'IPA espeak : le comparateur normalise (longueur, diacritiques) avant d'aligner.
- Safari/iOS exige le support `Range` pour l'audio : ne pas retirer `StreamingResponse` partiel de `/audio`.
