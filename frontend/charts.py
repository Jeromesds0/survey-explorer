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
    "label": "#52514e",
    "muted": "#898781",
    "low_base": "#b45309",
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
    "label": "#c3c2b7",
    "muted": "#898781",
    "low_base": "#fab219",
}
DARK_INK = "#0b0b0b"
LIGHT_INK = "#ffffff"

# Long labels are wrapped onto several lines. Lines are joined with LINE_BREAK, which the
# axis splits again when drawing the label.
LINE_BREAK = "|"
LINE_HEIGHT = 13
ROW_WRAP = 40
COLUMN_WRAP = 10
LABEL_LINES = f"length(split(datum.label, '{LINE_BREAK}'))"

# Tables fill the page, but stop growing at MAX_COLUMN_WIDTH per column so they don't look
# stretched on wide screens. Tables with more than MAX_FILL_COLUMNS columns would squash their
# headers on small screens, so they get fixed COLUMN_WIDTH columns and scroll sideways instead.
COLUMN_WIDTH = 70
MAX_COLUMN_WIDTH = 110
MAX_FILL_COLUMNS = 7
ROW_LABEL_SPACE = 280

# Column headers are two axes above the table: the column name, and under it the base,
# e.g. "(n=1,468)", smaller and muted (amber when the base is low). Column labels are stored
# as "name|n=1,468", with LOW_BASE_MARK on the end when the base is low.
HEADER_FONT_SIZE = 12
HEADER_LINE_HEIGHT = 15
BASE_FONT_SIZE = 10
BASE_ROW_HEIGHT = 16
LOW_BASE_MARK = "*"


def palette() -> dict:
    theme = st.context.theme
    return DARK if theme and theme.type == "dark" else LIGHT


def wrap(text: str, width: int) -> str:
    return LINE_BREAK.join(textwrap.wrap(text, width, break_long_words=False)) or text


# Extra lines of a wrapped label are drawn below the first one, so each label is shifted by
# its own number of lines: row labels up to stay centred on their row, column headers up so
# the last line sits just above the cells.
def row_axis() -> alt.Axis:
    return alt.Axis(
        labelExpr=f"split(datum.label, '{LINE_BREAK}')",
        labelLineHeight=LINE_HEIGHT,
        labelOffset={"expr": f"-({LABEL_LINES} - 1) * {LINE_HEIGHT / 2}"},
        labelLimit=320,
        ticks=False,
    )


def column_name_axis() -> alt.Axis:
    """Every line of the label except the last (the base), sitting above the base line."""
    return alt.Axis(
        orient="top",
        offset=BASE_ROW_HEIGHT,
        labelExpr=f"slice(split(datum.label, '{LINE_BREAK}'), 0, -1)",
        labelFontSize=HEADER_FONT_SIZE,
        labelLineHeight=HEADER_LINE_HEIGHT,
        labelPadding={"expr": f"({LABEL_LINES} - 2) * {HEADER_LINE_HEIGHT} + 4"},
        labelAngle=0,
        labelLimit=160,
        labelOverlap=False,
        domain=False,
        ticks=False,
    )


def column_base_axis(p: dict) -> alt.Axis:
    """Just the last line of the label, the base, shown as "(n=1,468)"."""
    base = f"peek(split(datum.label, '{LINE_BREAK}'))"
    is_low = f"indexof(datum.label, '{LOW_BASE_MARK}') >= 0"
    return alt.Axis(
        orient="top",
        labelExpr=f"'(' + replace({base}, '{LOW_BASE_MARK}', '') + ')'",
        labelFontSize=BASE_FONT_SIZE,
        labelColor={"condition": {"test": is_low, "value": p["low_base"]}, "value": p["muted"]},
        labelPadding=4,
        labelAngle=0,
        labelOverlap=False,
        domain=False,
        ticks=False,
    )


def row_step(rows: list[str]) -> alt.Step:
    """A fixed height per row, tall enough for the longest wrapped label.

    A fixed total height doesn't work: Streamlit fits the headers and legend into it too, so a
    table with only two rows (Yes/No) was squashed to nothing.
    """
    lines = max(row.count(LINE_BREAK) + 1 for row in rows)
    return alt.Step(20 + LINE_HEIGHT * lines)


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
        wrap(c, COLUMN_WRAP) + f"{LINE_BREAK}n={b:,}" + (LOW_BASE_MARK if b < low_base else "")
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
    """Horizontal bars for a single column (Total), in the order of the rows in df.

    Each bar is labelled with its value at the end. Percentages start at zero and run to just
    past the largest bar (with room for its label); net agree runs from -100 to +100.
    """
    p = palette()
    rows = list(dict.fromkeys(df["row"]))
    df = df.assign(label=df["value"].map(lambda v: cell_label(v, signed=diverging)))
    if diverging:
        x_scale, x_axis = alt.Scale(domain=[-100, 100]), alt.Axis(values=[-100, -50, 0, 50, 100])
        colour = alt.condition(
            "datum.value >= 0", alt.value(p["positive"]), alt.value(p["negative"])
        )
    else:
        top = min(100, max(df["value"].max(), 1) * 1.15)
        x_scale, x_axis = alt.Scale(domain=[0, top], nice=True), alt.Axis(tickCount=5)
        colour = alt.value(p["bar"])

    base = alt.Chart(df).encode(
        y=alt.Y("row:N", sort=rows, title=None, axis=row_axis()),
        x=alt.X("value:Q", title=title, scale=x_scale, axis=x_axis),
        tooltip=tooltip,
    )
    bars = base.mark_bar(cornerRadiusEnd=4).encode(color=colour)
    # Labels sit outside the end of each bar: right of positive bars, left of negative ones
    right = base.mark_text(align="left", dx=4, color=p["label"]).transform_filter(
        "datum.value >= 0"
    )
    left = base.mark_text(align="right", dx=-4, color=p["label"]).transform_filter(
        "datum.value < 0"
    )
    layers = [bars, right.encode(text="label:N"), left.encode(text="label:N")]
    if diverging:
        zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=p["rule"]).encode(x="x:Q")
        layers.append(zero)
    return (
        alt.layer(*layers)
        .properties(width="container", height=row_step(rows))
        .configure_scale(bandPaddingInner=0.35)
    )


def heatmap(df: pd.DataFrame, colour: alt.Scale, legend: str, tooltip: list, signed=False):
    """Shaded table: one cell per row and column, coloured by value and labelled with it."""
    p = palette()
    rows = list(dict.fromkeys(df["row"]))
    df = df.assign(label=df["value"].map(lambda v: cell_label(v, signed)))
    columns_in_order = list(dict.fromkeys(df["column"]))
    base = alt.Chart(df).encode(y=alt.Y("row:N", sort=rows, title=None, axis=row_axis()))
    # The two layers share one column scale but draw different axes: names and bases
    cells = base.mark_rect(cornerRadius=3, stroke=p["surface"], strokeWidth=2).encode(
        x=alt.X("column:N", sort=columns_in_order, title=None, axis=column_name_axis()),
        color=alt.Color(
            "value:Q",
            scale=colour,
            # Legend below the table so the columns get the full width
            legend=alt.Legend(title=legend, orient="bottom", gradientLength=240),
        ),
        tooltip=tooltip,
    )
    text = base.mark_text(fontSize=12).encode(
        x=alt.X("column:N", sort=columns_in_order, title=None, axis=column_base_axis(p)),
        text=alt.Text("label:N"),
        color=alt.condition("datum.light_text", alt.value(LIGHT_INK), alt.value(DARK_INK)),
        tooltip=tooltip,
    )
    table = (cells + text).resolve_axis(x="independent")
    columns = len(columns_in_order)
    if columns > MAX_FILL_COLUMNS:
        # Fixed-width columns so headers always fit. Scrolls sideways if needed (see app.py)
        return table.properties(width=alt.Step(COLUMN_WIDTH), height=row_step(rows))
    return table.properties(
        width="container",
        height=row_step(rows),
        usermeta={"max_width": ROW_LABEL_SPACE + columns * MAX_COLUMN_WIDTH},
    )


def display_width(chart) -> str | int:
    """How wide Streamlit should draw a chart.

    Tables fill the page up to their maximum width (Streamlit caps a pixel width at the page
    width), tables with fixed-width columns keep their own width, and bar charts fill the page.
    """
    if isinstance(chart.width, alt.Step):
        return "content"
    if chart.usermeta is not alt.Undefined:
        return chart.usermeta["max_width"]
    return "stretch"


def reliable_values(df: pd.DataFrame, low_base: int) -> pd.Series:
    """Values from cells with a base big enough to trust.

    Colour scales are fitted to these, so one respondent answering "Prefer not to say" can't
    stretch the scale and wash out every other column. Low-base cells still show, clamped to
    the end colour.
    """
    reliable = df.loc[df["base"] >= low_base, "value"]
    return reliable if len(reliable) else df["value"]


def sequential_scale(df: pd.DataFrame, p: dict, low_base: int) -> alt.Scale:
    top = max(reliable_values(df, low_base).max(), 1)
    df["light_text"] = needs_light_text(df["value"].clip(upper=top) / top, p)
    return alt.Scale(
        domain=[0, top],
        range=[p["scale_low"], p["scale_high"]],
        interpolate="lab",
        clamp=True,
    )


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
    colour = sequential_scale(df, palette(), result["low_base"])
    return heatmap(df, colour, "% of column", tooltip)


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
        return heatmap(df, sequential_scale(df, p, result["low_base"]), "% yes", tooltip)

    extent = max(reliable_values(df, result["low_base"]).abs().max(), 1)
    # "lab" blends straight through grey; the default blend drifts through pinks and purples
    colour = alt.Scale(
        domain=[-extent, 0, extent],
        range=[p["negative"], p["midpoint"], p["positive"]],
        interpolate="lab",
        clamp=True,
    )
    # Only the ends of the scale are dark enough for white text in light mode
    df["light_text"] = (p is DARK) | (df["value"].abs() / extent > 0.7)
    return heatmap(df, colour, "Net agree", tooltip, signed=True)
