# CLAUDE.md — DeutschAutoCorrect

Pipeline de correction automatique d'oraux d'allemand (collège). Lire `docs/BLUEPRINT.md` (architecture, décisions) et `docs/WORK_PACKAGES.md` (découpage) avant toute modification structurelle.

## Commandes

```bash
make install        # back (pip -e .[dev]) + front (npm ci)
make dev-back       # uvicorn app.main:app --reload  (http://localhost:8010 ; PORT=… pour changer)
make dev-front      # vite (http://localhost:5173, proxy /api → :8010)
make test           # pytest + vitest
make lint           # ruff + tsc
make demo           # lance le back avec moteurs mock et injecte un enregistrement de démo
make up / down / logs   # docker compose : image unique (front + API + moteurs réels), réseau hôte, port 8010
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
7. Catégories : `grammar|conjugation|vocabulary|pronunciation|text` (`text` = écart au texte de référence).

8. **Texte de référence** (récitation / lecture) : s'il est renseigné sur l'enregistrement, les mots de l'élève sont comparés à ce texte (`pipeline/reference.py`, erreurs `text`, une par mot oublié ou remplacé) et le correcteur grammatical n'est pas lancé.

## Conventions

- Python 3.11, typé, `ruff` (line-length 100). Modèles pydantic v2. Pas d'ORM : `sqlite3` + `db.py`.
- LLM : SDK `anthropic`, modèle par défaut `claude-opus-5-5`, **sortie structurée** via `output_config.format` (JSON schema) ; **pas de `tool_choice` forcé** (400 sur ce modèle), pas de `temperature`. Toujours valider/tolérer le JSON reçu.
- LLM local : backend `openai` (`OpenAICompatCorrector`, httpx sur `/v1/chat/completions`, `response_format` JSON schema, `temperature=0`) ; il vérifie le modèle servi avant chaque correction.
- Front : React 18 + TypeScript strict, pas de librairie UI ; CSS dans `src/styles/` avec variables (thème clair/sombre). Logique pure dans `src/lib/` (testée avec vitest).
- Barème : note = moyenne pondérée des critères (`earned/max` × coefficient ; coefficient par défaut = points max, soit la simple somme). Le critère `rhythm` est une *suggestion* (pauses longues, débit) que la saisie de l'enseignant remplace.
- Schéma SQLite : toute évolution passe par `Database._migrate` (`PRAGMA user_version`).
- Les identifiants d'erreur sont stables (`e_<hash>`), générés dans `pipeline/merge.py`.
- **Language: English by default.** Everything you produce is in English: code, identifiers, comments, commit messages, PRs, issues, documentation and interface text. The only exception is the conversation: reply in the language the maintainer writes in, so in French when they write in French. The existing interface and error explanations are in French.
- Commits : messages courts à l'impératif ; ne pas commiter `data/`, `node_modules/`, `.env`.

## Variables d'environnement

Voir `docs/BLUEPRINT.md` §2.6 et `.env.example`. Sans configuration, l'appli démarre en mode dégradé (mock/règles) — `GET /api/health` indique les moteurs actifs.

## Pièges connus

- Le port 8000 est souvent occupé par un serveur LLM local : l'API est sur 8010. `.env` se lit à la racine du repo.
- Les timecodes de mots de Whisper sont décalés de 150–300 ms : ne jamais découper l'audio mot à mot pour la prononciation (reconnaissance par segment + `split_by_words`).
- Le tokenizer du wav2vec2 de phonèmes exige `phonemizer` : on charge seulement le feature extractor et `vocab.json` (`ctc_decode`).
- `faster-whisper` hallucine sur les silences : le VAD est activé, et les segments à `no_speech_prob` élevé sont filtrés.
- Le wav2vec2 de phonèmes sort de l'IPA espeak : le comparateur normalise (longueur, diacritiques) avant d'aligner.
- Safari/iOS exige le support `Range` pour l'audio : ne pas retirer `StreamingResponse` partiel de `/audio`.
