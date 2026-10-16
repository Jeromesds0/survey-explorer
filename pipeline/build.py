"""Builds the warehouse: raw CSV -> cleaned tables in DuckDB.

    uv run python -m pipeline.build

Tables:
    respondents        one row per respondent, one column per question (cleaned)
    questions          label, group, type and base for each column in respondents
    question_options   answer options in display order
    data_quality_log   every check and fix the pipeline applied
    build_info         source file, hash, row counts and build time
Views:
    responses          long format: one row per respondent per answered question
"""

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from pipeline import codebook
from pipeline.clean import clean_survey, read_raw

RAW_FILE = Path("data/raw/tech_test_survey_data.csv")
WAREHOUSE = Path("warehouse/survey.duckdb")

RESPONSES_VIEW = """
    CREATE VIEW responses AS
    UNPIVOT (SELECT * EXCLUDE (age) FROM respondents)
    ON COLUMNS(* EXCLUDE (respondent_id))
    INTO NAME question_id VALUE answer
"""  # UNPIVOT drops nulls, so questions that weren't asked or answered don't appear


def metadata_tables() -> dict[str, pd.DataFrame]:
    questions = pd.DataFrame(
        [
            {
                "question_id": q.id,
                "label": q.label,
                "question_group": q.group,
                "kind": q.kind,
                "base": q.base,
                "derived": q.source is None,
                "position": i,
            }
            for i, q in enumerate(codebook.QUESTIONS)
        ]
    )
    options = pd.DataFrame(
        [
            {"question_id": q.id, "option": option, "position": i}
            for q in codebook.QUESTIONS
            for i, option in enumerate(q.options)
        ]
    )
    return {"questions": questions, "question_options": options}


def build(raw_file: Path = RAW_FILE, warehouse: Path = WAREHOUSE) -> dict:
    raw = read_raw(raw_file)
    respondents, log = clean_survey(raw)

    info = {
        "source_file": raw_file.name,
        "source_sha256": hashlib.sha256(raw_file.read_bytes()).hexdigest(),
        "raw_rows": len(raw),
        "clean_rows": len(respondents),
        "built_at": datetime.now(UTC).replace(tzinfo=None),
    }
    tables = {
        "respondents": respondents,
        **metadata_tables(),
        "data_quality_log": pd.DataFrame(log.to_records()).rename_axis("position").reset_index(),
        "build_info": pd.DataFrame([info]),
    }

    # Build into a temporary file and swap it in at the end, so a failed build never
    # leaves a half-written warehouse behind
    warehouse.parent.mkdir(parents=True, exist_ok=True)
    tmp = warehouse.with_name(warehouse.name + ".tmp")
    tmp.unlink(missing_ok=True)
    with duckdb.connect(str(tmp)) as con:
        for name, df in tables.items():
            con.register("staging", df)
            con.execute(f"CREATE TABLE {name} AS SELECT * FROM staging")
            con.unregister("staging")
        con.execute(RESPONSES_VIEW)

        loaded = con.execute("SELECT count(*), count(DISTINCT respondent_id) FROM respondents")
        rows, ids = loaded.fetchone()
        if rows != len(respondents) or ids != rows:
            raise RuntimeError(f"Load check failed: {rows} rows, {ids} distinct ids")
    tmp.replace(warehouse)
    return info


def main() -> None:
    info = build()
    print(
        f"Built {WAREHOUSE}: {info['clean_rows']} respondents "
        f"from {info['raw_rows']} raw rows ({info['source_file']})"
    )


if __name__ == "__main__":
    main()
