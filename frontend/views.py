"""The app's pages. Filters are set in the sidebar (app.py) and shared by every page."""

import io

import pandas as pd
import streamlit as st

import api_client
import charts

ANALYSABLE_KINDS = ("single", "yes_no", "agree_scale")
STATUS_LABELS = {"fixed": "🔧 Fixed", "warning": "⚠️ Warning", "passed": "✅ Passed"}


def questions_by_id() -> dict[str, dict]:
    return {q["id"]: q for q in api_client.questions()}


def current_filters() -> dict[str, list[str]]:
    return st.session_state.get("filters", {})


def describe_filters(filters: dict, questions: dict) -> str:
    if not filters:
        return "All respondents"
    return "; ".join(f"{questions[q]['label']}: {', '.join(v)}" for q, v in filters.items())


def question_picker(label: str, questions: dict, default: str | None, key: str, optional=False):
    ids = [q["id"] for q in questions.values() if q["kind"] in ANALYSABLE_KINDS]
    options = ([None] if optional else []) + ids
    return st.selectbox(
        label,
        options,
        index=options.index(default),
        format_func=lambda i: (
            "None (totals only)"
            if i is None
            else (f"{questions[i]['group']} › {questions[i]['label']}")
        ),
        key=key,
    )


def low_base_warning(columns: list[str], bases: list[int], threshold: int) -> None:
    low = [f"{c} (n={b})" for c, b in zip(columns, bases, strict=True) if b < threshold]
    if low:
        st.warning(
            f"Low base (fewer than {threshold} respondents): {', '.join(low)}. "
            "Treat these percentages with caution."
        )


def crosstab_page() -> None:
    questions = questions_by_id()
    filters = current_filters()

    st.title("Crosstabs")
    st.caption(
        "Pick a question and a breakdown. Percentages are of each column. "
        "n is the number of respondents in that column."
    )
    left, right = st.columns(2)
    with left:
        question_id = question_picker("Question", questions, "vote_intention", "xt_question")
    with right:
        breakdown_id = question_picker(
            "Breakdown", questions, "age_band", "xt_breakdown", optional=True
        )

    question = questions[question_id]
    result = api_client.crosstab(question_id, breakdown_id, filters)
    if not result["rows"]:
        st.info("No respondents match the current filters.")
        return

    st.subheader(question["label"])
    st.caption(f"Base: {question['base']} · Filters: {describe_filters(filters, questions)}")
    low_base_warning(result["columns"], result["bases"], result["low_base"])

    chart_tab, table_tab = st.tabs(["Chart", "Table"])
    with chart_tab:
        st.altair_chart(charts.crosstab_chart(result), width="stretch")
    with table_tab:
        show = st.segmented_control(
            "Show", ["Column %", "Counts"], default="Column %", key="xt_show"
        )
        values = result["counts"] if show == "Counts" else result["percents"]
        headers = [
            f"{c} (n={b:,})" for c, b in zip(result["columns"], result["bases"], strict=True)
        ]
        table = pd.DataFrame(values, index=result["rows"], columns=headers)
        table.index.name = question["label"]
        number_format = "%d" if show == "Counts" else "%.1f%%"
        st.dataframe(
            table,
            width="stretch",
            column_config={h: st.column_config.NumberColumn(format=number_format) for h in headers},
        )
        st.download_button(
            "Download table (CSV)",
            table.to_csv().encode("utf-8-sig"),
            file_name=f"{question_id}_by_{breakdown_id or 'total'}.csv",
            mime="text/csv",
        )


def grid_page() -> None:
    questions = questions_by_id()
    filters = current_filters()

    st.title("Attitudes and statements")
    kind = st.segmented_control(
        "Question set",
        ["agree_scale", "yes_no"],
        default="agree_scale",
        format_func={
            "agree_scale": "General attitudes",
            "yes_no": "Statements that apply to me",
        }.get,
        key="grid_kind",
    )
    kind = kind or "agree_scale"
    breakdown_id = question_picker(
        "Breakdown", questions, "eu_ref_vote", "grid_breakdown", optional=True
    )

    result = api_client.grid(kind, breakdown_id, filters)
    if not result["rows"]:
        st.info("No respondents match the current filters.")
        return

    if kind == "agree_scale":
        st.caption(
            "**Net agree** = % agree (strongly or slightly) minus % disagree (strongly or "
            "slightly). It runs from -100 (everyone disagrees) to +100 (everyone agrees). "
            "'Don't know' answers stay in the base."
        )
    else:
        st.caption(
            "% of respondents who said the statement applies to them. "
            "'I own more than one property' wasn't collected for part of fieldwork, "
            "so its base is smaller (see Data quality)."
        )
    st.caption(f"Filters: {describe_filters(filters, questions)}")
    low_base_warning(result["columns"], result["bases"][0], result["low_base"])

    labels = {q: questions[q]["label"] for q in result["rows"]}
    chart_tab, table_tab = st.tabs(["Chart", "Table"])
    with chart_tab:
        st.altair_chart(charts.grid_chart(result, labels), width="stretch")
    with table_tab:
        table = pd.DataFrame(
            result["values"], index=[labels[q] for q in result["rows"]], columns=result["columns"]
        )
        table.index.name = "Statement"
        number_format = "%+.1f" if kind == "agree_scale" else "%.1f%%"
        st.dataframe(
            table,
            width="stretch",
            column_config={
                c: st.column_config.NumberColumn(format=number_format) for c in table.columns
            },
        )
        bases = pd.DataFrame(result["bases"], index=table.index, columns=result["columns"])
        with st.expander("Bases (respondents behind each number)"):
            st.dataframe(bases, width="stretch")
        st.download_button(
            "Download table (CSV)",
            table.to_csv().encode("utf-8-sig"),
            file_name=f"{kind}_by_{breakdown_id or 'total'}.csv",
            mime="text/csv",
        )


def quality_page() -> None:
    report = api_client.data_quality()
    build, checks = report["build"], pd.DataFrame(report["checks"])

    st.title("Data quality")
    st.caption(
        "Every check and fix the pipeline applied to the raw survey file before loading it. "
        "Nothing is dropped or recoded without an entry here."
    )
    cols = st.columns(4)
    cols[0].metric("Raw rows", f"{build['raw_rows']:,}")
    cols[1].metric("Respondents after cleaning", f"{build['clean_rows']:,}")
    cols[2].metric("Fixes applied", int((checks["status"] == "fixed").sum()))
    cols[3].metric("Warnings", int((checks["status"] == "warning").sum()))
    st.caption(
        f"Source: `{build['source_file']}` (sha256 `{build['source_sha256'][:12]}…`) · "
        f"built {build['built_at'][:16].replace('T', ' ')} UTC"
    )

    # A static table so the long detail text wraps instead of being cut off
    checks["status"] = checks["status"].map(STATUS_LABELS)
    st.table(
        checks.rename(
            columns={
                "status": "Status",
                "step": "Step",
                "rows_affected": "Rows",
                "detail": "Detail",
            }
        ).set_index("Status")
    )

    st.subheader("Things to keep in mind")
    st.markdown(
        "- **Results are unweighted.** The file has no weighting variable, so figures describe "
        "this sample, not the UK population.\n"
        "- **EU referendum:** blank answers are shown as *Did not vote / not stated*. Half of "
        "18-24s are in this group, most of whom were too young to vote in 2016.\n"
        "- **Public sector area** was only asked of public sector and nationalised industry "
        "employees, so its base is smaller.\n"
        "- **'I own more than one property'** is missing for about 60% of respondents, in "
        "blocks of serial numbers. Treat it with caution."
    )


def data_page() -> None:
    questions = questions_by_id()
    filters = current_filters()

    st.title("Codebook and export")

    st.subheader("Export")
    n = api_client.count(filters)
    st.write(f"{n:,} respondents · Filters: {describe_filters(filters, questions)}")
    csv = api_client.export_csv(filters)
    st.download_button(
        "Download cleaned data (CSV)",
        csv,
        file_name="survey_respondents.csv",
        mime="text/csv",
        type="primary",
    )
    with st.expander("Preview first 50 rows"):
        st.dataframe(pd.read_csv(io.BytesIO(csv), nrows=50), hide_index=True, width="stretch")

    st.subheader("Codebook")
    st.caption("Column names in the export and the question each one holds.")
    codebook = pd.DataFrame(
        {
            "Column": q["id"],
            "Question": q["label"],
            "Group": q["group"],
            "Base": q["base"],
            "Answers (in order)": " | ".join(q["options"]),
        }
        for q in questions.values()
    )
    st.dataframe(codebook, hide_index=True, width="stretch")
