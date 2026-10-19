"""The app's pages. Filters are set in the sidebar (app.py) and shared by every page."""

import io

import pandas as pd
import streamlit as st

import api_client
import charts

ANALYSABLE_KINDS = ("single", "yes_no", "agree_scale")
STATUS_LABELS = {"fixed": "Fixed", "warning": "Warning", "passed": "Passed"}

# Breakdown groups on the attitudes and statements page. The 14 detailed income bands are left
# out: "Household income (grouped)" covers it with bases big enough to read.
BREAKDOWN_GROUPS = ("Demographics", "Politics")
SKIP_BREAKDOWNS = {"income"}


def questions_by_id() -> dict[str, dict]:
    return {q["id"]: q for q in api_client.questions()}


def current_filters() -> dict[str, list[str]]:
    return st.session_state.get("filters", {})


def describe_filters(filters: dict, questions: dict) -> str:
    if not filters:
        return "All respondents"
    return "; ".join(f"{questions[q]['label']}: {', '.join(v)}" for q, v in filters.items())


def question_picker(label: str, questions: dict, default: str, key: str) -> str:
    ids = [q["id"] for q in questions.values() if q["kind"] in ANALYSABLE_KINDS]
    return st.selectbox(
        label,
        ids,
        index=ids.index(default),
        format_func=lambda i: f"{questions[i]['group']} › {questions[i]['label']}",
        key=key,
    )


def low_base_warning(columns: list[str], bases: list[int], threshold: int) -> None:
    low = [f"{c} (n={b})" for c, b in zip(columns, bases, strict=True) if b < threshold]
    if low:
        st.warning(
            f"Low base (fewer than {threshold} respondents): {', '.join(low)}. "
            "Treat these percentages with caution."
        )


def show_chart(chart) -> None:
    st.altair_chart(chart, width=charts.display_width(chart))


def ranked(result: dict) -> dict:
    """Crosstab rows sorted by their Total percentage, largest first.

    Only for questions with no natural answer order (e.g. the most important goal).
    """
    order = sorted(range(len(result["rows"])), key=lambda i: -result["percents"][i][0])
    return result | {key: [result[key][i] for i in order] for key in ("rows", "counts", "percents")}


def crosstab_page() -> None:
    questions = questions_by_id()
    filters = current_filters()

    st.title("Crosstabs")
    overview_tab, explore_tab = st.tabs(["Overview", "Explore a question"])
    with overview_tab:
        overview(questions, filters)
    with explore_tab:
        explore_question(questions, filters)


def overview(questions: dict, filters: dict) -> None:
    """Headline results for the key questions, without having to pick anything."""
    st.caption(
        "The key questions at a glance. Use the sidebar filters to focus on a group, and "
        "'Explore a question' to see any of them split by demographics or politics. "
        f"Filters: {describe_filters(filters, questions)}"
    )

    st.subheader("What matters most")
    goal = api_client.crosstab("top_goal", None, filters)
    if not goal["rows"]:
        st.info("No respondents match the current filters.")
        return
    st.caption(f"{questions['top_goal']['label']}, most chosen first")
    low_base_warning(goal["columns"], goal["bases"], goal["low_base"])
    show_chart(charts.crosstab_chart(ranked(goal)))

    st.subheader("Views on the big issues")
    attitudes = api_client.grid("agree_scale", None, filters)
    st.caption(
        "Net agree: % agree minus % disagree, from -100 (everyone disagrees) to +100 "
        "(everyone agrees)"
    )
    labels = {q: questions[q]["label"] for q in attitudes["rows"]}
    show_chart(charts.grid_chart(attitudes, labels))

    for question_id in ("vote_intention", "eu_ref_vote"):
        result = api_client.crosstab(question_id, None, filters)
        st.subheader(questions[question_id]["label"])
        show_chart(charts.crosstab_chart(result))


def explore_question(questions: dict, filters: dict) -> None:
    """One question, split by every breakdown in a group, so splits don't need picking."""
    question_id = question_picker("Question", questions, "vote_intention", "xt_question")
    question = questions[question_id]
    st.caption(
        f"Base: {question['base']} · Filters: {describe_filters(filters, questions)} · "
        "Percentages are of each column; n is the number of respondents in that column."
    )
    breakdown_sections(
        questions,
        key="xt",
        render=lambda breakdown_id: crosstab_section(question_id, breakdown_id, questions, filters),
        exclude=question_id,
    )


def crosstab_section(
    question_id: str, breakdown_id: str | None, questions: dict, filters: dict
) -> None:
    """Chart and table for one question, split by one breakdown (or totals only)."""
    question = questions[question_id]
    result = api_client.crosstab(question_id, breakdown_id, filters)
    if not result["rows"]:
        st.info("No respondents match the current filters.")
        return
    if breakdown_id and questions[breakdown_id]["base"] != "All respondents":
        st.caption(f"{questions[breakdown_id]['label']} base: {questions[breakdown_id]['base']}")
    low_base_warning(result["columns"], result["bases"], result["low_base"])

    chart_tab, table_tab = st.tabs(["Chart", "Table"])
    with chart_tab:
        show_chart(charts.crosstab_chart(result))
    with table_tab:
        show = st.segmented_control(
            "Show",
            ["Column %", "Counts"],
            default="Column %",
            key=f"xt_show_{breakdown_id}",
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
            key=f"xt_download_{breakdown_id}",
        )


def breakdown_sections(questions: dict, key: str, render, exclude: str | None = None) -> None:
    """Split by Overall (totals), or by every breakdown in a group, one section each.

    A button bar rather than tabs: tabs would build every group's charts on each click.
    """
    group = st.segmented_control(
        "Split by", ["Overall", *BREAKDOWN_GROUPS], default="Overall", key=f"{key}_group"
    )
    if group in (None, "Overall"):
        render(None)
        return
    breakdowns = [
        q
        for q in questions.values()
        if q["group"] == group
        and q["kind"] in ANALYSABLE_KINDS
        and q["id"] not in SKIP_BREAKDOWNS
        and q["id"] != exclude
    ]
    for breakdown in breakdowns:
        with st.container(border=True):
            if section_heading(breakdown["label"], key=f"{key}_{breakdown['id']}"):
                render(breakdown["id"])


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
    breakdown_sections(
        questions,
        key="grid",
        render=lambda breakdown_id: grid_section(kind, breakdown_id, questions, filters),
    )


def toggle(state_key: str) -> None:
    st.session_state[state_key] = not st.session_state.get(state_key, True)


def section_heading(title: str, key: str) -> bool:
    """A section title with a magnifier button to hide (-) or show (+) the section.

    Sections start open. Returns whether the section is open.
    """
    state_key = f"open_{key}"
    is_open = st.session_state.get(state_key, True)
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        st.button(
            "",
            icon=":material/zoom_out:" if is_open else ":material/zoom_in:",
            help="Hide this section" if is_open else "Show this section",
            type="tertiary",
            key=f"toggle_{key}",
            on_click=toggle,
            args=(state_key,),
        )
        st.markdown(f"**{title}**")
    return is_open


def grid_section(kind: str, breakdown_id: str | None, questions: dict, filters: dict) -> None:
    """Chart and table for one question set, split by one breakdown (or totals only)."""
    result = api_client.grid(kind, breakdown_id, filters)
    if not result["rows"]:
        st.info("No respondents match the current filters.")
        return
    if breakdown_id and questions[breakdown_id]["base"] != "All respondents":
        st.caption(f"Base: {questions[breakdown_id]['base']}")
    low_base_warning(result["columns"], result["bases"][0], result["low_base"])

    labels = {q: questions[q]["label"] for q in result["rows"]}
    chart_tab, table_tab = st.tabs(["Chart", "Table"])
    with chart_tab:
        show_chart(charts.grid_chart(result, labels))
    with table_tab:
        # Column base = everyone in the column (one statement has a smaller base, see above)
        column_bases = [max(column) for column in zip(*result["bases"], strict=True)]
        headers = [f"{c} (n={b:,})" for c, b in zip(result["columns"], column_bases, strict=True)]
        table = pd.DataFrame(
            result["values"], index=[labels[q] for q in result["rows"]], columns=headers
        )
        table.index.name = "Statement"
        number_format = "%+.1f" if kind == "agree_scale" else "%.1f%%"
        st.dataframe(
            table,
            width="stretch",
            column_config={h: st.column_config.NumberColumn(format=number_format) for h in headers},
        )
        st.download_button(
            "Download table (CSV)",
            table.to_csv().encode("utf-8-sig"),
            file_name=f"{kind}_by_{breakdown_id or 'total'}.csv",
            mime="text/csv",
            key=f"grid_download_{kind}_{breakdown_id}",
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
    cols[1].metric("Respondents", f"{build['clean_rows']:,}")
    cols[2].metric("Fixes applied", int((checks["status"] == "fixed").sum()))
    cols[3].metric("Warnings", int((checks["status"] == "warning").sum()))
    st.caption(
        f"Source: `{build['source_file']}` (sha256 `{build['source_sha256'][:12]}…`) · "
        f"built {build['built_at'][:16].replace('T', ' ')} UTC"
    )

    # A static table so the long detail text wraps instead of being cut off. Raw column names
    # are one long word, so allow a line break after each underscore (zero-width space).
    checks["status"] = checks["status"].map(STATUS_LABELS)
    checks["detail"] = checks["detail"].str.replace("_", "_​")
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
