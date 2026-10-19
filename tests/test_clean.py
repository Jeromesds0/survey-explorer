from pathlib import Path

import pandas as pd
import pytest

from pipeline import codebook
from pipeline.clean import EU_REF_NO_VOTE, clean_survey, read_raw
from pipeline.quality import DataQualityError

RAW_FILE = Path("data/raw/tech_test_survey_data.csv")


def make_raw(*rows: dict) -> pd.DataFrame:
    """Build a raw-format DataFrame. Each dict overrides answers (by short id) for one row."""
    records = []
    for i, overrides in enumerate(rows, start=1):
        answers = {q.id: q.options[0] for q in codebook.QUESTIONS if q.source and q.options}
        answers |= {q.id: "No" for q in codebook.QUESTIONS if q.kind == "yes_no"}
        # Varied attitude answers, so a default row isn't flagged as straightlining
        attitudes = [q for q in codebook.QUESTIONS if q.kind == "agree_scale"]
        answers |= {q.id: q.options[n % 5] for n, q in enumerate(attitudes)}
        answers |= {
            "respondent_id": str(i),
            "age": "21",
            "income": "ú14,001 to ú21,000",  # as it appears in the raw export
            "public_sector_area": "",  # private sector employee, so not asked
        }
        answers |= overrides
        record = {q.source: answers[q.id] for q in codebook.QUESTIONS if q.source}
        record |= {column: "No" for column in codebook.DROPPED_COLUMNS}
        records.append(record)
    return pd.DataFrame(records, dtype=str)


def statuses(log, step):
    return [c.status for c in log.checks if c.step == step]


def test_valid_row_is_cleaned():
    df, log = clean_survey(make_raw({}))

    assert len(df) == 1
    assert list(df.columns) == [q.id for q in codebook.QUESTIONS]
    assert df.loc[0, "age"] == 21
    assert "warning" not in [c.status for c in log.checks]


def test_pound_sign_is_fixed():
    df, _ = clean_survey(make_raw({"income": "ú83,001 or more"}))

    assert df.loc[0, "income"] == "£83,001 or more"


def test_exact_duplicate_rows_are_removed():
    df, log = clean_survey(make_raw({"respondent_id": "7"}, {"respondent_id": "7"}))

    assert len(df) == 1
    assert statuses(log, "duplicate rows") == ["fixed"]


def test_same_id_with_different_answers_fails():
    raw = make_raw({"respondent_id": "7"}, {"respondent_id": "7", "gender": "Male"})

    with pytest.raises(DataQualityError, match="conflicting"):
        clean_survey(raw)


def test_routed_question_blank_means_not_asked():
    df, _ = clean_survey(
        make_raw(
            {},
            {
                "employer_type": "Other public sector employer (e.g. Central Government)",
                "public_sector_area": "Health and social care",
            },
        )
    )

    assert pd.isna(df.loc[0, "public_sector_area"])
    assert df.loc[1, "public_sector_area"] == "Health and social care"


def test_eu_ref_blank_is_kept_as_a_category():
    df, _ = clean_survey(make_raw({"eu_ref_vote": ""}))

    assert df.loc[0, "eu_ref_vote"] == EU_REF_NO_VOTE


def test_property_blank_is_missing_not_no():
    df, log = clean_survey(make_raw({"stmt_multiple_properties": ""}))

    assert pd.isna(df.loc[0, "stmt_multiple_properties"])
    assert statuses(log, "missing values").count("warning") == 1


def test_unexpected_blank_fails():
    with pytest.raises(DataQualityError, match="blank"):
        clean_survey(make_raw({"gender": ""}))


def test_answer_not_in_codebook_fails():
    with pytest.raises(DataQualityError, match="vote_intention"):
        clean_survey(make_raw({"vote_intention": "Monster Raving Loony"}))


def test_missing_column_fails():
    raw = make_raw({}).drop(columns="gender")

    with pytest.raises(DataQualityError, match="Missing: \\['gender'\\]"):
        clean_survey(raw)


def test_non_numeric_age_fails():
    with pytest.raises(DataQualityError, match="age"):
        clean_survey(make_raw({"age": "twenty"}))


def test_derived_columns():
    df, _ = clean_survey(
        make_raw(
            {"region": "Scotland", "income": "ú83,001 or more"},
            {"region": "London", "income": "Up to ú7,000"},
        )
    )

    assert df["nation"].tolist() == ["Scotland", "England"]
    assert df["income_group"].tolist() == ["£41,001 or more", "Up to £21,000"]


def test_inconsistent_answers_are_logged_not_changed():
    df, log = clean_survey(make_raw({"age_band": "65+", "age": "30"}))

    assert df.loc[0, "age_band"] == "65+"
    assert "warning" in statuses(log, "consistency")


def test_state_pension_below_60_is_logged():
    _, log = clean_survey(
        make_raw(
            {"work_status": "Retired on a state pension only", "age_band": "35-44", "age": "44"}
        )
    )

    assert "warning" in statuses(log, "consistency")


def test_same_answer_to_every_attitude_is_flagged_not_removed():
    all_dont_know = {q.id: "Don't know" for q in codebook.QUESTIONS if q.kind == "agree_scale"}
    df, log = clean_survey(make_raw(all_dont_know, {}))

    assert len(df) == 2
    assert statuses(log, "response quality") == ["warning"]
    warning = next(c for c in log.checks if c.step == "response quality")
    assert warning.rows_affected == 1


def test_raw_file_end_to_end():
    df, log = clean_survey(read_raw(RAW_FILE))

    assert len(df) == 1468
    assert df["respondent_id"].is_unique
    assert not df["income"].str.contains("ú").any()
    assert df["public_sector_area"].notna().sum() == 345
