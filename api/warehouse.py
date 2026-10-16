import os
from pathlib import Path

import duckdb

from api.models import Question

DEFAULT_PATH = Path("warehouse/survey.duckdb")


def warehouse_path() -> Path:
    return Path(os.environ.get("SURVEY_WAREHOUSE", DEFAULT_PATH))


class Warehouse:
    """Read-only connection to the DuckDB file built by the pipeline.

    Question metadata is loaded once at startup. It doubles as the allowlist of column names
    that requests are allowed to reference.
    """

    def __init__(self, path: Path):
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found. Build it with: uv run python -m pipeline.build"
            )
        self._con = duckdb.connect(str(path), read_only=True)
        self.questions = self._load_questions()

    def _load_questions(self) -> dict[str, Question]:
        rows = self._con.execute(
            """
            SELECT q.question_id, q.label, q.question_group, q.kind, q.base, q.derived,
                   list(o.option ORDER BY o.position) FILTER (WHERE o.option IS NOT NULL)
            FROM questions q
            LEFT JOIN question_options o USING (question_id)
            GROUP BY q.question_id, q.label, q.question_group, q.kind, q.base, q.derived,
                     q.position
            ORDER BY q.position
            """
        ).fetchall()
        questions = [
            Question(
                id=id,
                label=label,
                group=group,
                kind=kind,
                base=base,
                derived=derived,
                options=options or [],
            )
            for id, label, group, kind, base, derived, options in rows
        ]
        return {q.id: q for q in questions}

    def cursor(self) -> duckdb.DuckDBPyConnection:
        # One cursor per request: DuckDB connections shouldn't be shared between threads
        return self._con.cursor()

    def close(self) -> None:
        self._con.close()
