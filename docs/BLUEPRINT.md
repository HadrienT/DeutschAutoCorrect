# Blueprint — DeutschAutoCorrect

Correction automatique d'enregistrements oraux d'allemand (collège, niveau A1–B1).
Entrée : un audio d'élève (+ interventions de l'enseignant, parfois en français, bruit de classe).
Sortie : transcription **fidèle** (erreurs conservées), liste d'erreurs classées par catégorie avec timecodes cliquables, note calculée selon un barème paramétrable.

---

## 1. Problèmes difficiles et décisions

| # | Difficulté | Décision |
|---|-----------|----------|
| 1 | Les ASR (Whisper) « corrigent » ce qu'ils entendent (prior du modèle de langue) → les erreurs disparaissent du transcript | `condition_on_previous_text=False`, pas de `initial_prompt` grammatical, langue forcée **par segment** (pas de détection globale), températures basses, conservation des probabilités mot à mot. Les mots à faible confiance sont signalés au correcteur. Une 2ᵉ voie **acoustique** (phonèmes) est indépendante du modèle de langue. |
| 2 | Mélange allemand / français (élève demande de l'aide) | Détection de langue **par segment** (ASR + heuristique lexicale de secours). Segments `fr` → exclus de la notation, affichés atténués. |
| 3 | Interventions de l'enseignant (« Silence ! », « Ruhe bitte », correction orale) | Classification de rôle par segment : `student` / `teacher` / `other`. Signaux : diarisation (optionnelle), langue, lexique d'injonctions FR/DE, locuteur dominant en allemand = élève. L'enseignant peut **reclasser** un segment dans l'UI → recalcul. |
| 4 | Prononciation = catégorie la plus importante et la plus dure | Comparaison **phonémique** : phonèmes attendus (G2P espeak-ng, à partir du mot reconnu ou de la correction) vs phonèmes réellement prononcés (reconnaisseur CTC `wav2vec2-xlsr-53-espeak`) mot par mot, alignement par distance d'édition **pondérée par des règles d'erreurs typiques de francophones** (ch-Laut, ü/ö, h, r, w/v, z, ei/ie, Auslautverhärtung, e muet…). + signal de faible confiance ASR. |
| 5 | Grammaire / conjugaison / vocabulaire | LLM (Claude) en sortie structurée JSON sur le transcript fidèle annoté (confiance, pauses). Repli hors-ligne : moteur de règles minimal (accord sujet-verbe, auxiliaire, genre de noms courants, mots français dans la phrase allemande). |
| 6 | Reproductibilité / tests sans GPU ni clé API | Chaque étape est une **interface** avec une implémentation `mock`/`rules`/`none`. Le pipeline complet tourne en CI et en démo sans modèle. |
| 7 | Barème variable selon les enseignants | Barème = donnée (JSON) : critères, points max, pénalités par gravité, plafonds, politique des erreurs répétées, critères manuels et de volume. Le calcul est une **fonction pure** rejouée à chaque modification. |
| 8 | L'IA se trompe | Chaque erreur est **confirmable / rejetable / modifiable** par l'enseignant ; la note se recalcule en direct. Les corrections sont persistées. |

## 2. Architecture

```
┌────────────┐  upload   ┌─────────────────────────── Backend (FastAPI) ────────────────────────────┐
│  Frontend  │──────────▶│ API REST  ─▶ JobRunner (thread pool) ─▶ Pipeline ─▶ SQLite + fichiers    │
│ React/Vite │◀──────────│   │                                        │                              │
└────────────┘  JSON/    │   └─▶ Scoring (pur)                        ├─ 1 audio    ffmpeg → wav 16k │
   audio stream          │                                            ├─ 2 asr      faster-whisper   │
                         │                                            ├─ 3 segments langue + rôle    │
                         │                                            ├─ 4 prononciation phonèmes    │
                         │                                            ├─ 5 correction LLM / règles   │
                         │                                            └─ 6 fusion & timecodes        │
                         └───────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Pipeline (orchestrateur `app/pipeline/orchestrator.py`)

1. **audio** — `ffmpeg` → WAV mono 16 kHz ; durée ; pics de forme d'onde (pour l'UI).
2. **asr** — `AsrEngine.transcribe(wav) -> list[Segment]` avec mots horodatés + probabilités. Impl. : `faster_whisper`, `mock`.
3. **segments** — `LanguageDetector` (par segment), `RoleClassifier` (student/teacher/other), marquage `graded` (élève + allemand uniquement).
4. **pronunciation** — `PronunciationEngine.analyze(wav, words) -> list[WordPhonemes]` puis `compare` (pur, testé) → erreurs `pronunciation`. Impl. : `wav2vec2`, `none`, `mock`.
5. **correction** — `Corrector.correct(student_segments) -> list[DetectedError]` (grammar / conjugation / vocabulary). Impl. : `anthropic`, `rules`.
6. **merge** — dédoublonnage (même mot, même catégorie), ancrage temporel (début/fin du mot fautif), tri, identifiants stables.

Chaque étape publie `stage` + `progress` (0–100) dans la table `recordings` ; l'UI interroge `GET /api/recordings/{id}`.

### 2.2 Modèle de données (pydantic, `app/models.py`)

- `Word{text,start,end,prob}`
- `Segment{id,start,end,text,language: de|fr|other, role: student|teacher|other, speaker?, graded: bool, words[]}`
- `ErrorCategory = grammar | conjugation | vocabulary | pronunciation`
- `Severity = minor | major`
- `DetectedError{id, category, subtype, severity, segment_id, start, end, heard, expected, explanation, confidence, source, status: pending|confirmed|rejected, note}`
- `Analysis{segments[], errors[], stats{duration,student_words,speech_ratio,...}, engines{asr,corrector,pronunciation}}`
- `Rubric{id,name,total_points,rounding,repeat_policy,criteria[]}` ; `Criterion{id,label,kind: errors|volume|manual,category?,max_points,penalty_minor,penalty_major,min_words_tiers[],manual_value?}`
- `Grade{total,out_of,criteria[{id,label,earned,max,detail}],rounded}`

### 2.3 Stockage

SQLite (stdlib `sqlite3`, pas d'ORM) : `recordings(id,title,student_name,filename,status,stage,progress,error,duration,created_at,rubric_id,analysis_json,manual_json)`, `rubrics(id,name,json,created_at)`. Fichiers audio dans `data/audio/{id}/`. L'analyse est un document JSON : les éditions d'erreurs sont des patchs sur ce document.

### 2.4 API REST

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/health` | état + moteurs actifs |
| POST | `/api/recordings` (multipart: file, title, student_name, rubric_id) | crée + lance le job |
| GET | `/api/recordings` | liste |
| GET | `/api/recordings/{id}` | détail : statut, analyse, note |
| DELETE | `/api/recordings/{id}` | supprime |
| GET | `/api/recordings/{id}/audio` | flux audio (Range supporté) |
| GET | `/api/recordings/{id}/peaks` | pics de forme d'onde |
| POST | `/api/recordings/{id}/reanalyze` | relance le pipeline |
| PATCH | `/api/recordings/{id}/errors/{eid}` | statut / catégorie / gravité / note |
| POST | `/api/recordings/{id}/errors` | ajout manuel d'une erreur |
| PATCH | `/api/recordings/{id}/segments/{sid}` | reclasser rôle / langue / graded |
| PUT | `/api/recordings/{id}/rubric` | change le barème appliqué + notes manuelles |
| GET | `/api/recordings/{id}/grade` | note recalculée |
| GET | `/api/recordings/{id}/export.{csv,json}` | export |
| GET/POST/PUT/DELETE | `/api/rubrics[/{id}]` | CRUD barèmes |
| POST | `/api/grading/preview` | calcule une note pour (analyse, barème) sans persister |

### 2.5 Frontend (React + TypeScript + Vite, CSS maison, FR)

- **Bibliothèque** : dépôt par glisser-déposer, liste avec statut/progress/note.
- **Vue enregistrement** (cœur) : lecteur + forme d'onde avec marqueurs d'erreurs colorés par catégorie ; transcript (élève en clair, enseignant/français atténués) avec mots fautifs surlignés ; panneau « Erreurs » groupées par catégorie, chaque ligne = timecode cliquable (seek + lecture 1,5 s autour) + « entendu → attendu » + explication + ✓/✗/✎ ; carte **Note** live ; filtres ; raccourcis clavier (espace, J/K erreur préc./suiv., C/R confirmer/rejeter).
- **Barèmes** : éditeur visuel (critères, points, pénalités, plafonds), aperçu live sur un enregistrement, import/export JSON.
- Thème clair/sombre, responsive, impression (bilan élève).

### 2.6 Configuration (variables d'environnement, préfixe `DAC_`)

`DAC_ASR_BACKEND=faster-whisper|mock`, `DAC_WHISPER_MODEL=large-v3`, `DAC_WHISPER_DEVICE=auto`, `DAC_PRON_BACKEND=wav2vec2|none|mock`, `DAC_CORRECTOR_BACKEND=anthropic|rules`, `DAC_ANTHROPIC_MODEL=claude-opus-5-5`, `ANTHROPIC_API_KEY`, `DAC_DATA_DIR=./data`. Défaut sûr : `mock/none/rules` si les dépendances lourdes sont absentes (le `/api/health` l'indique).

## 3. Notation — règles de calcul

Pour chaque critère `errors` : on prend les erreurs **non rejetées** de la catégorie, sur segments `graded` ; `repeat_policy` ∈ `count_all | once_per_subtype | once_per_expected` (une même faute répétée ne pénalise qu'une fois) ; points = `max_points − Σ pénalités`, bornés à `[0, max]` ; option `cap_deduction`. Critère `volume` : paliers par nombre de mots d'élève (`[{min_words, points}]`). Critère `manual` : valeur saisie par l'enseignant. Total = Σ ; mise à l'échelle sur `total_points` ; arrondi (`none|0.5|1`).

## 4. Qualité

- pytest : scoring (cas limites), comparaison phonémique, classification rôle/langue, règles, pipeline bout-en-bout avec moteurs mock, API (TestClient).
- vitest : utilitaires front (regroupement, formatage temps, seek).
- Lint : ruff (back), tsc strict + eslint léger (front). Build front vérifié.
- Test visuel Playwright (Chromium présent) sur données de démonstration.

## 5. Hors périmètre v1 (extensions documentées)

Évaluation de l'intonation/débit fin, multi-élèves dans un même fichier avec identification vocale, authentification/multi-enseignants, file de jobs distribuée.
