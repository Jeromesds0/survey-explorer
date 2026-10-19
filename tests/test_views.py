from views import ranked


def test_ranked_sorts_rows_by_total_and_keeps_them_aligned():
    result = {
        "rows": ["A", "B", "C"],
        "columns": ["Total", "Male"],
        "counts": [[1, 1], [5, 2], [3, 3]],
        "percents": [[10.0, 20.0], [50.0, 40.0], [30.0, 40.0]],
    }

    out = ranked(result)

    assert out["rows"] == ["B", "C", "A"]
    assert out["counts"] == [[5, 2], [3, 3], [1, 1]]
    assert out["percents"][0] == [50.0, 40.0]
    assert out["columns"] == ["Total", "Male"]
