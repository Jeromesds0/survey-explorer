import duckdb
import pytest

from pipeline.build import RAW_FILE, build


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    warehouse = tmp_path_factory.mktemp("warehouse") / "survey.duckdb"
    build(RAW_FILE, warehouse)
    with duckdb.connect(str(warehouse), read_only=True) as con:
        yield con


def scalar(con, sql):
    return con.execute(sql).fetchone()[0]


def test_one_row_per_respondent(con):
    assert scalar(con, "SELECT count(*) FROM respondents") == 1468
    assert scalar(con, "SELECT count(DISTINCT respondent_id) FROM respondents") == 1468


def test_not_asked_is_stored_as_null(con):
    nulls = "SELECT count(*) FROM respondents WHERE public_sector_area IS NULL"
    assert scalar(con, nulls) == 1123


def test_every_column_has_metadata(con):
    columns = {row[0] for row in con.execute("DESCRIBE respondents").fetchall()}
    questions = {row[0] for row in con.execute("SELECT question_id FROM questions").fetchall()}
    assert columns == questions


def test_options_keep_codebook_order(con):
    first, last = con.execute(
        """
        SELECT first(option ORDER BY position), last(option ORDER BY position)
        FROM question_options WHERE question_id = 'income'
        """
    ).fetchone()
    assert (first, last) == ("Up to £7,000", "Prefer not to answer")


def test_responses_view_skips_unanswered(con):
    answered = "SELECT count(*) FROM responses WHERE question_id = 'public_sector_area'"
    assert scalar(con, answered) == 345


def test_build_info_records_source(con):
    raw_rows, clean_rows, sha = con.execute(
        "SELECT raw_rows, clean_rows, source_sha256 FROM build_info"
    ).fetchone()
    assert (raw_rows, clean_rows) == (1499, 1468)
    assert sha.startswith("d54aff6d")


def test_quality_log_is_loaded(con):
    assert scalar(con, "SELECT count(*) FROM data_quality_log WHERE status = 'fixed'") > 0
