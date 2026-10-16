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
    spec = charts.crosstab_chart(CROSSTAB).to_dict()

    assert spec["layer"][0]["mark"]["type"] == "rect"


def test_total_only_crosstab_is_a_bar_chart():
    total_only = {
        **CROSSTAB,
        "columns": ["Total"],
        "bases": [100],
        "counts": [[30], [70]],
        "percents": [[30.0], [70.0]],
    }
    spec = charts.crosstab_chart(total_only).to_dict()

    assert spec["mark"]["type"] == "bar"
