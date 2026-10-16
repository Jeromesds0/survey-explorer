"""Request validation and the SQL behind each endpoint.

Column names can't be bound as SQL parameters, so every question id in a request is checked
against the question metadata before it is put into a query. Answer values are always passed
as bound parameters.
"""

import duckdb
import pandas as pd

from api.models import Filters, Question

TOTAL = "Total"
LOW_BASE = 50
ANALYSABLE_KINDS = {"single", "yes_no", "agree_scale"}

# For each grid type: what the value means, answers that count +1 and answers that count -1
GRID_METRICS = {
    "agree_scale": (
        "Net agree (% agree minus % disagree)",
        {"Agree strongly", "Agree slightly"},
        {"Disagree slightly", "Disagree strongly"},
    ),
    "yes_no": ("% saying yes", {"Yes"}, set()),
}


class InvalidRequest(Exception):
    pass


def resolve_question(questions: dict[str, Question], question_id: str) -> Question:
    question = questions.get(question_id)
    if question is None or question.kind not in ANALYSABLE_KINDS:
        raise InvalidRequest(f"'{question_id}' is not a question that can be analysed")
    return question


def resolve_filters(questions: dict[str, Question], filters: Filters) -> Filters:
    resolved = {}
    for question_id, values in filters.items():
        question = resolve_question(questions, question_id)
        unknown = set(values) - set(question.options)
        if unknown:
            raise InvalidRequest(f"Unknown answers for '{question_id}': {sorted(unknown)}")
        if values:  # an empty selection means no filter
            resolved[question_id] = values
    return resolved


def where_sql(filters: Filters) -> tuple[str, dict]:
    """Builds `list_contains($f0, region) AND ...` with the selected answers as parameters."""
    clauses, params = ["TRUE"], {}
    for i, (column, values) in enumerate(filters.items()):
        clauses.append(f"list_contains($f{i}, {column})")
        params[f"f{i}"] = values
    return " AND ".join(clauses), params


def in_codebook_order(values, options: list[str]) -> list[str]:
    present = set(values)
    return [option for option in options if option in present]


def with_total(df: pd.DataFrame, breakdown: Question | None) -> pd.DataFrame:
    """Repeats every row under a "Total" breakdown.

    Respondents with no answer for the breakdown question (e.g. not asked) still count
    towards the total.
    """
    parts = [df.assign(breakdown=TOTAL)]
    if breakdown:
        parts.append(df.dropna(subset=["breakdown"]))
    return pd.concat(parts)


def crosstab(
    cur: duckdb.DuckDBPyConnection, question: Question, breakdown: Question | None, filters: Filters
) -> dict:
    where, params = where_sql(filters)
    breakdown_sql = breakdown.id if breakdown else "NULL"
    counts = cur.execute(
        f"""
        SELECT {question.id} AS answer, {breakdown_sql} AS breakdown, count(*) AS n
        FROM respondents
        WHERE {question.id} IS NOT NULL AND {where}
        GROUP BY ALL
        """,
        params,
    ).df()

    table = with_total(counts, breakdown).pivot_table(
        index="answer", columns="breakdown", values="n", aggfunc="sum", fill_value=0
    )
    rows = in_codebook_order(table.index, question.options)
    columns = [TOTAL] + (in_codebook_order(table.columns, breakdown.options) if breakdown else [])
    table = table.reindex(index=rows, columns=columns, fill_value=0).astype(int)
    bases = table.sum()

    return {
        "question": question.id,
        "breakdown": breakdown.id if breakdown else None,
        "rows": rows,
        "columns": columns,
        "bases": bases.tolist(),
        "counts": table.values.tolist(),
        "percents": (table / bases * 100).round(1).values.tolist(),
        "low_base": LOW_BASE,
    }


def grid(
    cur: duckdb.DuckDBPyConnection,
    questions: list[Question],
    kind: str,
    breakdown: Question | None,
    filters: Filters,
) -> dict:
    """One summary number per statement in a grid (e.g. net agree), split by a breakdown."""
    metric, positive, negative = GRID_METRICS[kind]
    where, params = where_sql(filters)
    params["ids"] = [q.id for q in questions]
    breakdown_sql = breakdown.id if breakdown else "NULL"
    counts = cur.execute(
        f"""
        SELECT question_id, answer, {breakdown_sql} AS breakdown, count(*) AS n
        FROM responses
        JOIN respondents USING (respondent_id)
        WHERE list_contains($ids, question_id) AND {where}
        GROUP BY ALL
        """,
        params,
    ).df()

    # +1 for a positive answer, -1 for a negative one, 0 otherwise (e.g. Don't know).
    # The value is then points / base * 100.
    sign = counts["answer"].isin(positive).astype(int) - counts["answer"].isin(negative).astype(int)
    counts["points"] = sign * counts["n"]
    summary = (
        with_total(counts, breakdown)
        .groupby(["question_id", "breakdown"])[["n", "points"]]
        .sum()
        .unstack("breakdown")
    )

    rows = [q.id for q in questions if q.id in summary.index]
    columns = [TOTAL] + (
        in_codebook_order(summary["n"].columns, breakdown.options) if breakdown else []
    )
    bases = summary["n"].reindex(index=rows, columns=columns).fillna(0).astype(int)
    values = (summary["points"].reindex(index=rows, columns=columns) / bases * 100).round(1)

    return {
        "kind": kind,
        "metric": metric,
        "rows": rows,
        "columns": columns,
        "bases": bases.values.tolist(),
        "values": values.astype(object).where(values.notna(), None).values.tolist(),
        "low_base": LOW_BASE,
    }


def count(cur: duckdb.DuckDBPyConnection, filters: Filters) -> int:
    where, params = where_sql(filters)
    return cur.execute(f"SELECT count(*) FROM respondents WHERE {where}", params).fetchone()[0]


def export_csv(cur: duckdb.DuckDBPyConnection, filters: Filters) -> bytes:
    where, params = where_sql(filters)
    df = cur.execute(f"SELECT * FROM respondents WHERE {where} ORDER BY respondent_id", params).df()
    # utf-8-sig adds a byte order mark so Excel shows £ correctly
    return df.to_csv(index=False).encode("utf-8-sig")


def records(cur: duckdb.DuckDBPyConnection, sql: str) -> list[dict]:
    result = cur.execute(sql)
    names = [column[0] for column in result.description]
    return [dict(zip(names, row, strict=True)) for row in result.fetchall()]


def data_quality(cur: duckdb.DuckDBPyConnection) -> dict:
    return {
        "build": records(cur, "SELECT * FROM build_info")[0],
        "checks": records(
            cur,
            "SELECT step, status, rows_affected, detail FROM data_quality_log ORDER BY position",
        ),
    }
