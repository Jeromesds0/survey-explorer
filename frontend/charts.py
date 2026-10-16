"""Altair charts for the survey app.

Colour has one job per chart:
  - a single series (one bar per answer) uses one blue
  - percentages in a crosstab use one blue scale, light to dark
  - net agree (positive or negative) uses blue and orange with a grey midpoint

Blue vs orange rather than blue vs red: in a UK politics survey, blue vs red would read as
Conservative vs Labour.
"""

import math
import textwrap

import altair as alt
import pandas as pd
import streamlit as st

# Low values sit close to the background in both modes, so the scale runs light -> dark on a
# light background and dark -> light on a dark one
LIGHT = {
    "bar": "#2a78d6",
    "scale_low": "#cde2fb",
    "scale_high": "#104281",
    "positive": "#256abf",
    "negative": "#eb6834",
    "midpoint": "#f0efec",
    "surface": "#ffffff",
    "rule": "#c3c2b7",
}
DARK = {
    "bar": "#3987e5",
    "scale_low": "#0d366b",
    "scale_high": "#b7d3f6",
    "positive": "#3987e5",
    "negative": "#d95926",
    "midpoint": "#383835",
    "surface": "#0e1117",
    "rule": "#383835",
}
DARK_INK = "#0b0b0b"
LIGHT_INK = "#ffffff"

# Long labels are wrapped onto several lines. Lines are joined with LINE_BREAK, which the
# axis splits again when drawing the label.
LINE_BREAK = "|"
ROW_WRAP = 40
COLUMN_WRAP = 12


def palette() -> dict:
    theme = st.context.theme
    return DARK if theme and theme.type == "dark" else LIGHT


def wrap(text: str, width: int) -> str:
    return LINE_BREAK.join(textwrap.wrap(text, width)) or text


def axis(**kwargs) -> alt.Axis:
    return alt.Axis(labelExpr=f"split(datum.label, '{LINE_BREAK}')", **kwargs)


def chart_height(rows: list[str]) -> int:
    lines = max(row.count(LINE_BREAK) + 1 for row in rows)
    return len(rows) * (20 + 13 * lines) + 60


def cell_label(value: float, signed: bool) -> str:
    """Whole number, rounded half away from zero like Excel. Never shows "-0"."""
    whole = math.floor(abs(value) + 0.5) * (1 if value >= 0 else -1)
    return f"{whole:+d}" if signed and whole else str(whole)


def needs_light_text(strength: pd.Series, p: dict) -> pd.Series:
    """Which cells on a light-to-dark scale need white text, given value / max (0 to 1).

    In light mode cells get darker as values rise. In dark mode the scale is reversed so low
    values fade into the background, which means the low cells are the dark ones.
    """
    return strength > 0.55 if p is LIGHT else strength <= 0.55


def to_long(
    rows: list[str],
    columns: list[str],
    values: list[list[float | None]],
    bases: list[list[int]],
    low_base: int,
) -> pd.DataFrame:
    """One record per cell. Cells with no value (nobody in the base) are left out."""
    column_bases = [max(bases[i][j] for i in range(len(rows))) for j in range(len(columns))]
    column_labels = [
        wrap(c, COLUMN_WRAP) + f"{LINE_BREAK}n={b:,}" + (" (low)" if b < low_base else "")
        for c, b in zip(columns, column_bases, strict=True)
    ]
    return pd.DataFrame(
        [
            {
                "row": wrap(row, ROW_WRAP),
                "row_full": row,
                "column": column_labels[j],
                "column_full": columns[j],
                "value": values[i][j],
                "base": bases[i][j],
            }
            for i, row in enumerate(rows)
            for j in range(len(columns))
            if values[i][j] is not None
        ]
    )


def bar_chart(df: pd.DataFrame, title: str, tooltip: list, diverging: bool = False):
    """Horizontal bars for a single column (Total), in the order of the rows in df."""
    p = palette()
    rows = list(dict.fromkeys(df["row"]))
    colour = (
        alt.condition("datum.value >= 0", alt.value(p["positive"]), alt.value(p["negative"]))
        if diverging
        else alt.value(p["bar"])
    )
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            y=alt.Y("row:N", sort=rows, title=None, axis=axis(labelLimit=320, ticks=False)),
            x=alt.X(
                "value:Q",
                title=title,
                scale=alt.Scale(domain=[-100, 100] if diverging else [0, 100]),
            ),
            color=colour,
            tooltip=tooltip,
        )
    )
    if diverging:
        zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=p["rule"]).encode(x="x:Q")
        chart = chart + zero
    return chart.properties(width="container", height=chart_height(rows)).configure_scale(
        bandPaddingInner=0.35
    )


def heatmap(df: pd.DataFrame, colour: alt.Scale, legend: str, tooltip: list, signed=False):
    """Shaded table: one cell per row and column, coloured by value and labelled with it."""
    p = palette()
    rows = list(dict.fromkeys(df["row"]))
    df = df.assign(label=df["value"].map(lambda v: cell_label(v, signed)))
    base = alt.Chart(df).encode(
        x=alt.X(
            "column:N",
            sort=list(dict.fromkeys(df["column"])),
            title=None,
            axis=axis(
                orient="top", labelAngle=0, labelLimit=160, labelOverlap=False, labelPadding=6
            ),
        ),
        y=alt.Y("row:N", sort=rows, title=None, axis=axis(labelLimit=320, ticks=False)),
    )
    cells = base.mark_rect(cornerRadius=3, stroke=p["surface"], strokeWidth=2).encode(
        color=alt.Color("value:Q", scale=colour, title=legend),
        tooltip=tooltip,
    )
    text = base.mark_text(fontSize=12).encode(
        text=alt.Text("label:N"),
        color=alt.condition("datum.light_text", alt.value(LIGHT_INK), alt.value(DARK_INK)),
        tooltip=tooltip,
    )
    return (cells + text).properties(width="container", height=chart_height(rows))


def sequential_scale(df: pd.DataFrame, p: dict) -> alt.Scale:
    top = max(df["value"].max(), 1)
    df["light_text"] = needs_light_text(df["value"] / top, p)
    return alt.Scale(domain=[0, top], range=[p["scale_low"], p["scale_high"]], interpolate="lab")


def crosstab_chart(result: dict):
    rows = result["rows"]
    df = to_long(
        rows,
        result["columns"],
        result["percents"],
        [result["bases"]] * len(rows),
        result["low_base"],
    )
    df["count"] = [count for row in result["counts"] for count in row]
    tooltip = [
        alt.Tooltip("row_full:N", title="Answer"),
        alt.Tooltip("column_full:N", title="Column"),
        alt.Tooltip("value:Q", title="% of column", format=".1f"),
        alt.Tooltip("count:Q", title="Respondents"),
        alt.Tooltip("base:Q", title="Column base"),
    ]
    if len(result["columns"]) == 1:
        return bar_chart(df, "% of respondents", tooltip)
    return heatmap(df, sequential_scale(df, palette()), "% of column", tooltip)


def grid_chart(result: dict, labels: dict[str, str]):
    """Net agree or % yes for each statement in a grid, split by a breakdown."""
    agree = result["kind"] == "agree_scale"
    df = to_long(
        [labels[q] for q in result["rows"]],
        result["columns"],
        result["values"],
        result["bases"],
        result["low_base"],
    )
    tooltip = [
        alt.Tooltip("row_full:N", title="Statement"),
        alt.Tooltip("column_full:N", title="Column"),
        alt.Tooltip("value:Q", title=result["metric"], format="+.1f" if agree else ".1f"),
        alt.Tooltip("base:Q", title="Base"),
    ]
    if len(result["columns"]) == 1:
        return bar_chart(
            df.sort_values("value", ascending=False), result["metric"], tooltip, diverging=agree
        )

    p = palette()
    if not agree:
        return heatmap(df, sequential_scale(df, p), "% yes", tooltip)

    extent = max(df["value"].abs().max(), 1)
    # "lab" blends straight through grey; the default blend drifts through pinks and purples
    colour = alt.Scale(
        domain=[-extent, 0, extent],
        range=[p["negative"], p["midpoint"], p["positive"]],
        interpolate="lab",
    )
    # Only the ends of the scale are dark enough for white text in light mode
    df["light_text"] = (p is DARK) | (df["value"].abs() / extent > 0.7)
    return heatmap(df, colour, "Net agree", tooltip, signed=True)
