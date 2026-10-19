import pytest

import charts

CROSSTAB = {
    "rows": ["Yes", "No"],
    "columns": ["Total", "Male", "Female"],
    "bases": [100, 40, 60],
    "counts": [[30, 10, 20], [70, 30, 40]],
    "percents": [[30.0, 25.0, 33.3], [70.0, 75.0, 66.7]],
    "low_base": 50,
}


@pytest.mark.parametrize(
    ("value", "signed", "expected"),
    [
        (12.5, False, "13"),  # half rounds away from zero, as in Excel
        (-0.4, True, "0"),  # never "-0"
        (-2.5, True, "-3"),
        (7.2, True, "+7"),
    ],
)
def test_cell_label(value, signed, expected):
    assert charts.cell_label(value, signed) == expected


def test_crosstab_chart_builds():
    chart = charts.crosstab_chart(CROSSTAB)
    spec = chart.to_dict()

    assert spec["layer"][0]["mark"]["type"] == "rect"
    # Fills the page, up to a maximum width for 3 columns
    assert charts.display_width(chart) == charts.ROW_LABEL_SPACE + 3 * charts.MAX_COLUMN_WIDTH


def test_two_row_table_has_a_height_per_row():
    # A fixed total height squashed Yes/No tables to nothing
    spec = charts.crosstab_chart(CROSSTAB).to_dict()

    assert spec["height"] == {"step": 33}


def test_table_with_many_columns_keeps_fixed_columns():
    columns = ["Total"] + [f"Region {i}" for i in range(11)]
    many = {
        **CROSSTAB,
        "columns": columns,
        "bases": [100] * 12,
        "counts": [[30] * 12, [70] * 12],
        "percents": [[30.0] * 12, [70.0] * 12],
    }
    chart = charts.crosstab_chart(many)

    assert charts.display_width(chart) == "content"


def test_total_only_crosstab_is_a_bar_chart():
    total_only = {
        **CROSSTAB,
        "columns": ["Total"],
        "bases": [100],
        "counts": [[30], [70]],
        "percents": [[30.0], [70.0]],
    }
    chart = charts.crosstab_chart(total_only)

    layers = chart.to_dict()["layer"]
    assert layers[0]["mark"]["type"] == "bar"
    assert layers[1]["mark"]["type"] == "text"  # value labels at the bar ends
    assert charts.display_width(chart) == "stretch"


def test_colour_scale_ignores_low_base_columns():
    # "Male" has a base of 40 (below 50) and the most extreme value; it mustn't set the scale
    low_base_extreme = {**CROSSTAB, "percents": [[30.0, 99.0, 33.3], [70.0, 1.0, 66.7]]}
    spec = charts.crosstab_chart(low_base_extreme).to_dict()
    scale = spec["layer"][0]["encoding"]["color"]["scale"]

    assert scale["domain"] == [0, 70.0]
    assert scale["clamp"] is True


def test_wrapping_keeps_words_whole():
    assert charts.wrap("House person, housewife, househusband", 10) == (
        "House|person,|housewife,|househusband"
    )
