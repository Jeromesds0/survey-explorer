# CLAUDE.md

Instructions for AI coding agents working in this repo.

## Project

A data application for analysts exploring a ~1,500 respondent UK political attitudes survey.

```
data/raw (CSV) -> pipeline/ (pandas) -> warehouse/survey.duckdb -> api/ (FastAPI) -> frontend/ (Streamlit)
```

## Commands

- `uv run start.py` - build the warehouse, start the API (port 8000) and UI (port 8501)
- `uv run python -m pipeline.build` - rebuild `warehouse/survey.duckdb` from the raw data
- `uv run pytest` - run the tests
- `uv run ruff check .` and `uv run ruff format .` - lint and format

## Layout

- `data/raw/` - source files exactly as delivered. Never edit, re-save or reformat them.
- `pipeline/` - codebook, cleaning and loading. All data fixes happen here and nowhere else.
- `api/` - FastAPI app with read-only access to the warehouse.
- `frontend/` - Streamlit app. Talks to the API over HTTP only. Must not import from
  `pipeline/` or open the database directly.
- `docs/` - profiling notes and design decisions.

## Data rules

- Read `docs/data-profiling.md` before changing cleaning logic. Blanks mean different things
  in different questions (not asked, did not vote, collection gap).
- Every cleaning step is a named function, writes an entry to the data quality log, and has a
  test. Never drop or recode rows silently.
- Category order comes from the codebook. Never sort answer options alphabetically.
- Percentages are always shown with their base (n). Bases under 50 are flagged.

## Code rules

- SQL column names only come from the codebook allowlist. Values are always bound parameters.
- Ask before adding a new dependency.
- Keep functions small and typed. Follow the existing style.

## Workflow

- Work in small steps and stop at logical commit points for review.
- Do not commit or write commit messages. The author reviews the diff and commits.
- Do not push or change git remotes.
