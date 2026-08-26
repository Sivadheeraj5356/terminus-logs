# Text Retrieval Benchmark: Incident Corpus

## The Retrieval Task

The corpus at `/app/data/incident_transcript.txt` is a multi-day production incident transcript. Build a natural-language retrieval index over this corpus, evaluate its ranking quality against held-out queries, and expose the retrieval and evaluation interfaces so they can be graded.

## Corpus Preparation

- Split the transcript into overlapping word-windowed passages. The passage count must reach at least 150.
- Build a text retrieval index over the passages using only the Python standard library — no `scikit-learn`, no vector embedding APIs, no network at runtime. Allowed runtime packages are `fastapi`, `uvicorn`, `pydantic`, and `aiofiles`.

## Ranking and Answer Synthesis

For a natural-language question, produce a ranked list of the top-k passages and a short synthesised answer:

- Each returned passage carries a citation label `[N]` (1-indexed), a similarity score in `[0, 1]`, and a `highlighted_snippet` — a ~200-character excerpt of the passage with every non-stopword query token wrapped in `<mark>...</mark>` (case-insensitive, word-boundary match).
- The synthesised answer references at least two distinct passages via inline `[N]` markers (e.g. `Based on [1] and [2], …`).
- Ranking must be deterministic — the same question always yields the same ordering.
- Passages must be returned in descending order of similarity score.

## Ranking Quality

Retrieval is scored on both agent-defined and verifier-controlled queries:

- Your evaluation endpoint runs the index against at least 5 held-out questions you define and reports Mean Reciprocal Rank (`mrr`), Hit-at-K (`hit_rate`), `n_questions`, and per-question `results` (`question`, `hit_at_k`, `reciprocal_rank`, `retrieved_passage_ids`). `mrr` must exceed **0.7**.
- Verifier-controlled queries run against the same index at grading time. These questions are not visible at build time and may use different wording than the source passages, so ranking must remain robust to vocabulary mismatch.

## Reference

| Item | Specification |
|------|-------------|
| Corpus path | `/app/data/incident_transcript.txt` |
| Port | 8000 (start uvicorn as a background daemon before the solution script exits; the grader will not start it) |
| Retrieval index constraints | ≥ 150 overlapping passages, standard library only, deterministic |
| Similarity score | float in `[0, 1]` |
| Answer synthesis | `[N]` citations inline; ≥ 2 distinct citations referenced |
| `highlighted_snippet` | ~200 chars with `<mark>` around non-stopword query tokens |
| `mrr` bar | > 0.7 |
| `GET /health` | `{"status": "ok", "chunks_loaded": <int>}` |
| `POST /query` | `{"question": str, "top_k": int}` → `{"question", "passages", "answer"}`. HTTP 400 on empty question. Passage fields: `id`, `text`, `score`, `citation`, `highlighted_snippet`. |
| `GET /passages` | JSON array: `id` (int), `preview` (str, first 200 chars) |
| `GET /validate` | See "Ranking Quality" |
| `GET /history` | JSON array, newest first: `question` (str), `answer` (str) |
| Dashboard | Static bundle at `/app/static/` served at `/`. Page title and h1 both "RAG Incident Dashboard". Includes a Validate tab with a "Run Evaluation" button that triggers `/validate`. Pre-installed node modules at `/opt/frontend-deps/node_modules` — symlink, do not run `npm install`. |
| Dashboard `data-testid`s | `question-input`, `submit-btn`, `results-area`, `passage-card`, `confidence-score`, `validation-panel`, `loading-indicator` |
| Loading indicator behaviour | Stays in the DOM; toggle visibility via CSS, not conditional rendering. The backend responds in milliseconds, so enforce a minimum visible duration of ~300ms or schedule the fetch after DOM commit (`requestAnimationFrame`) so the in-flight state is observable. |
