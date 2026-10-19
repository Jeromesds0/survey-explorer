# Survey Explorer

A browser tool for analysts to explore a UK political attitudes survey (1,468 respondents)
without writing code. A tested pipeline cleans the raw export into DuckDB, a FastAPI service
serves it, and a Streamlit app gives analysts crosstabs, attitude summaries, a data quality
report and clean exports.

## Running it

You need [uv](https://docs.astral.sh/uv/getting-started/installation/), which installs the right
Python and the exact dependency versions.

```bash
uv run start.py
```

This rebuilds the database from the raw CSV and opens the app at http://localhost:8501 (API docs
at http://localhost:8000/docs). Ctrl+C stops it. Run the tests with `uv run pytest`.

Without uv, using Python 3.12+: `pip install -r requirements.txt`, then `python start.py`.

## What it does

- **Overview**: headline results with nothing to set up.
- **Explore a question**: any question, split by every demographic or political breakdown at once.
- **Attitudes and statements**: all 11 attitude statements (net agree) and 16 "applies to me"
  statements in one view, with the same splits.
- **Filters**: one set of sidebar filters across every page, with a live respondent count.
- **Data quality**: everything the pipeline fixed or flagged in the raw file.
- **Export**: filtered, cleaned data as an Excel-friendly CSV, plus a codebook.

Every percentage is shown with its base (n), and bases under 50 are flagged.

## How it works

```
data/raw (CSV) → pipeline/ (pandas) → warehouse/survey.duckdb → api/ (FastAPI) → frontend/ (Streamlit)
```

- **Pipeline**: a codebook maps each raw column to a short name, label and answer order. Cleaning
  is a series of small steps, each logged and tested. It stops on anything unsafe (a changed
  column, an unknown answer), fixes what's clear, and flags what isn't.
- **DuckDB**: an analytical database in a single file. No server to run, which suits a
  read-only, aggregation-heavy app.
- **API**: read-only access to the warehouse. Column names come from an allowlist and values are
  always bound parameters.
- **Frontend**: Streamlit, talking to the API only.

## Problems in the raw data

Details in [docs/data-profiling.md](docs/data-profiling.md).

- 31 duplicate rows (one respondent repeated 32 times), so 1,499 rows became 1,468 respondents
- `£` mis-encoded as `ú` in every income band
- A routed question, blank for everyone not asked, now uses the correct base
- EU referendum blanks kept as "Did not vote / not stated": dropping them would skew the sample
  older
- A question with 60% missing answers in blocks of serial numbers, flagged rather than treated
  as "No"
- 38 respondents gave the same answer to all 11 attitude statements (mostly "Don't know"),
  a sign of low-effort answering: flagged with their IDs rather than removed
- No weighting variable, so results are unweighted

## What I built, what I left out and why

I focused on what slows analysts down with survey data: raw data they can't trust, wrong bases,
answers in the wrong order, and rebuilding the same crosstabs by hand.

Left out, with what I'd do next:

- **Weighting**: no weights in the file. I'd add rim weighting to population targets.
- **Significance testing**: column-proportion tests to flag real differences. The next feature.
- **Saved views and user accounts**: useful for a team, but not needed to show the approach.
- **Deployment**: runs locally with one command. Next would be Docker and a hosted instance.
- **Natural language queries (LLM)**: correct numbers matter more. If added, the model would call
  the tested API rather than write its own SQL.

## In production

Load the cleaned tables into the team's shared warehouse, run the pipeline from an orchestrator
when new files land, treat the codebook as a data contract with alerts on failure, and deploy
the API and app behind single sign-on with CI on every change.

## Use of AI

Built with Claude Code as a coding agent. I set the direction, reviewed the changes and made the
commits. [CLAUDE.md](CLAUDE.md) sets the rules it worked to, such as never modifying raw data
and testing every cleaning step.
