"""Turns the raw survey export into one clean row per respondent.

Each step is a small function that fixes or checks one thing and records it in the quality log.
See docs/data-profiling.md for the evidence behind each decision.
"""

from pathlib import Path

import pandas as pd

from pipeline import codebook
from pipeline.quality import DataQualityError, QualityLog

PUBLIC_SECTOR_EMPLOYERS = {
    "Other public sector employer (e.g. Central Government)",
    "Nationalised industry or public corporation (e.g. Post Office)",
}
EU_REF_NO_VOTE = "Did not vote / not stated"

NATIONS = {"Scotland": "Scotland", "Wales": "Wales"}  # every other region is in England

INCOME_GROUPS = {
    "Up to £7,000": "Up to £21,000",
    "£7,001 to £14,000": "Up to £21,000",
    "£14,001 to £21,000": "Up to £21,000",
    "£21,001 to £28,000": "£21,001 to £41,000",
    "£28,001 to £34,000": "£21,001 to £41,000",
    "£34,001 to £41,000": "£21,001 to £41,000",
    "Prefer not to answer": "Prefer not to answer",
}  # every other band is £41,001 or more

AGE_BANDS = {
    "18-24": (18, 24),
    "25-34": (25, 34),
    "35-44": (35, 44),
    "45-54": (45, 54),
    "55-64": (55, 64),
    "65+": (65, 200),
}


def read_raw(path: Path) -> pd.DataFrame:
    # Everything is read as text so pandas doesn't guess types or turn values into NaN.
    # Blanks stay as "" until a step decides what they mean.
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")


def check_schema(df: pd.DataFrame, log: QualityLog) -> None:
    expected = set(codebook.source_columns()) | set(codebook.DROPPED_COLUMNS)
    missing = expected - set(df.columns)
    unexpected = set(df.columns) - expected
    if missing or unexpected:
        raise DataQualityError(
            f"Columns don't match the codebook. Missing: {sorted(missing)}. "
            f"Unexpected: {sorted(unexpected)}"
        )
    log.add("schema", "passed", 0, f"All {len(df.columns)} columns match the codebook")


def rename_columns(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    for column, reason in codebook.DROPPED_COLUMNS.items():
        values = sorted(df[column].unique())
        log.add("drop column", "fixed", 0, f"Dropped {column} (values: {values}). {reason}")
    return df.drop(columns=list(codebook.DROPPED_COLUMNS)).rename(columns=codebook.source_columns())


def drop_duplicate_rows(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    is_copy = df.duplicated()
    copied_ids = sorted({int(i) for i in df.loc[is_copy, "respondent_id"]})
    df = df[~is_copy].reset_index(drop=True)

    # Same ID with different answers can't be resolved automatically
    clashes = df.loc[df["respondent_id"].duplicated(), "respondent_id"].unique()
    if len(clashes):
        raise DataQualityError(f"Respondent IDs with conflicting answers: {sorted(clashes)}")

    if is_copy.sum():
        log.add(
            "duplicate rows",
            "fixed",
            is_copy.sum(),
            f"Removed {is_copy.sum()} exact duplicate rows (respondent IDs: {copied_ids})",
        )
    else:
        log.add("duplicate rows", "passed", 0, "No duplicate rows")
    return df


def fix_pound_sign(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    # The £ byte (0xA3) was decoded as code page 850 upstream, where 0xA3 is "ú"
    df = df.copy()
    broken = df["income"].str.contains("ú", regex=False)
    df["income"] = df["income"].str.replace("ú", "£", regex=False)

    still_broken = [c for c in df.columns if df[c].str.contains("ú", regex=False).any()]
    if still_broken:
        raise DataQualityError(f"Unexpected 'ú' characters in columns: {still_broken}")

    log.add("encoding", "fixed", broken.sum(), "Replaced 'ú' with '£' in income bands")
    return df


def recode_routed_question(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    # public_sector_area was only asked of public sector employees. Blank means "not asked".
    df = df.copy()
    asked = df["employer_type"].isin(PUBLIC_SECTOR_EMPLOYERS)
    blank = df["public_sector_area"].eq("")

    answered_but_not_asked = int((~asked & ~blank).sum())
    blank_but_asked = int((asked & blank).sum())
    if answered_but_not_asked or blank_but_asked:
        log.add(
            "routing",
            "warning",
            answered_but_not_asked + blank_but_asked,
            f"public_sector_area doesn't follow the routing: {answered_but_not_asked} answered "
            f"but not asked, {blank_but_asked} asked but blank",
        )

    df.loc[blank, "public_sector_area"] = None
    log.add(
        "routing",
        "fixed",
        blank.sum(),
        f"public_sector_area is only asked of public sector employees ({asked.sum()}). "
        f"Set {blank.sum()} blanks to null (not asked)",
    )
    return df


def recode_eu_ref_blanks(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    # Blanks are concentrated in the youngest respondents (too young to vote in 2016), so
    # dropping them would skew the sample older. Keep them as their own category.
    df = df.copy()
    blank = df["eu_ref_vote"].eq("")
    df.loc[blank, "eu_ref_vote"] = EU_REF_NO_VOTE
    log.add(
        "missing values", "fixed", blank.sum(), f"eu_ref_vote blanks recoded to '{EU_REF_NO_VOTE}'"
    )
    return df


def flag_missing_property_answers(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    # Unlike every other statement, this one has blanks, and they cluster in serial number
    # ranges. Treat as not collected rather than assuming "No".
    df = df.copy()
    blank = df["stmt_multiple_properties"].eq("")
    df.loc[blank, "stmt_multiple_properties"] = None
    if blank.sum():
        log.add(
            "missing values",
            "warning",
            blank.sum(),
            f"stmt_multiple_properties is blank for {blank.sum()} respondents "
            f"({blank.mean():.0%}). Treated as missing, not 'No'",
        )
    return df


def check_no_other_blanks(df: pd.DataFrame, log: QualityLog) -> None:
    blank_counts = df.eq("").sum()
    blank_counts = blank_counts[blank_counts > 0]
    if len(blank_counts):
        raise DataQualityError(f"Unexpected blank values: {blank_counts.to_dict()}")
    log.add("missing values", "passed", 0, "No unexpected blanks in any other column")


def check_allowed_values(df: pd.DataFrame, log: QualityLog) -> None:
    problems = {}
    for q in codebook.QUESTIONS:
        if q.source is None or not q.options:
            continue
        unexpected = set(df[q.id].dropna()) - set(q.options)
        if unexpected:
            problems[q.id] = sorted(unexpected)
    if problems:
        raise DataQualityError(f"Values not in the codebook: {problems}")
    log.add("allowed values", "passed", 0, "Every answer matches a codebook option")


def cast_types(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    df = df.copy()
    for column in ("respondent_id", "age"):
        if not df[column].str.fullmatch(r"\d+").all():
            raise DataQualityError(f"{column} contains non-numeric values")
        df[column] = df[column].astype("int64")

    out_of_range = ~df["age"].between(18, 110)
    if out_of_range.any():
        raise DataQualityError(f"Ages outside 18-110: {sorted(df.loc[out_of_range, 'age'])}")
    log.add("types", "passed", 0, "respondent_id and age are whole numbers; ages are 18-110")
    return df


def add_derived_columns(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    df = df.copy()
    df["nation"] = df["region"].map(NATIONS).fillna("England")
    df["income_group"] = df["income"].map(INCOME_GROUPS).fillna("£41,001 or more")
    log.add(
        "derived columns",
        "fixed",
        0,
        "Added nation (from region) and income_group (income bands grouped for larger bases)",
    )
    return df


def check_consistency(df: pd.DataFrame, log: QualityLog) -> None:
    """Cross-question checks. These are logged, not fixed, as there's no safe correction."""
    low = df["age_band"].map(lambda b: AGE_BANDS[b][0])
    high = df["age_band"].map(lambda b: AGE_BANDS[b][1])
    statements = [c for c in df.columns if c.startswith("stmt_") and c != "stmt_none"]
    working = df["work_status"].str.startswith("Working")

    # rule -> rows that break it
    rules = {
        "Age band matches actual age": ~df["age"].between(low, high),
        "SNP voters live in Scotland": (df["vote_intention"] == "SNP")
        & (df["region"] != "Scotland"),
        "Plaid Cymru voters live in Wales": (df["vote_intention"] == "Plaid Cymru")
        & (df["region"] != "Wales"),
        "'None of these' is never ticked alongside a statement": (df["stmt_none"] == "Yes")
        & df[statements].eq("Yes").any(axis=1),
        "People currently working don't say they have never worked": working
        & (df["employer_type"] == "Have never worked"),
    }
    for rule, broken in rules.items():
        n = int(broken.sum())
        if n:
            ids = sorted(df.loc[broken, "respondent_id"])
            log.add("consistency", "warning", n, f"{rule}: {n} exceptions (respondent IDs: {ids})")
        else:
            log.add("consistency", "passed", 0, rule)


def clean_survey(raw: pd.DataFrame) -> tuple[pd.DataFrame, QualityLog]:
    log = QualityLog()
    check_schema(raw, log)
    df = rename_columns(raw, log)
    df = drop_duplicate_rows(df, log)
    df = fix_pound_sign(df, log)
    df = recode_routed_question(df, log)
    df = recode_eu_ref_blanks(df, log)
    df = flag_missing_property_answers(df, log)
    check_no_other_blanks(df, log)
    check_allowed_values(df, log)
    df = cast_types(df, log)
    df = add_derived_columns(df, log)
    check_consistency(df, log)

    column_order = [q.id for q in codebook.QUESTIONS]
    return df[column_order], log
