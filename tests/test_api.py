import pytest
from fastapi.testclient import TestClient

from api.main import app
from pipeline.build import RAW_FILE, build


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    warehouse = tmp_path_factory.mktemp("warehouse") / "survey.duckdb"
    build(RAW_FILE, warehouse)
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("SURVEY_WAREHOUSE", str(warehouse))
        with TestClient(app) as client:
            yield client


def post(client, path, payload):
    response = client.post(path, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_questions_keep_codebook_order(client):
    questions = {q["id"]: q for q in client.get("/questions").json()}

    assert questions["income"]["options"][0] == "Up to £7,000"
    assert questions["age_band"]["options"][-1] == "65+"


def test_crosstab_without_breakdown(client):
    body = post(client, "/crosstab", {"question": "eu_ref_vote"})

    assert body["columns"] == ["Total"]
    assert body["bases"] == [1468]
    assert body["rows"] == ["Remain", "Leave", "Did not vote / not stated"]


def test_crosstab_columns_add_up(client):
    body = post(client, "/crosstab", {"question": "vote_intention", "breakdown": "age_band"})

    assert body["columns"] == ["Total", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
    assert sum(body["bases"][1:]) == body["bases"][0]
    for column in range(len(body["columns"])):
        assert sum(row[column] for row in body["percents"]) == pytest.approx(100, abs=0.5)


def test_filters_reduce_the_base(client):
    body = post(client, "/crosstab", {"question": "gender", "filters": {"region": ["Wales"]}})

    assert body["bases"] == [72]


def test_count_matches_filters(client):
    assert post(client, "/count", {})["respondents"] == 1468
    assert post(client, "/count", {"filters": {"region": ["Wales"]}})["respondents"] == 72


def test_empty_filter_is_ignored(client):
    body = post(client, "/crosstab", {"question": "gender", "filters": {"region": []}})

    assert body["bases"] == [1468]


def test_routed_question_uses_its_own_base(client):
    body = post(client, "/crosstab", {"question": "public_sector_area"})

    assert body["bases"] == [345]


def test_total_includes_people_not_asked_the_breakdown(client):
    body = post(client, "/crosstab", {"question": "gender", "breakdown": "public_sector_area"})

    assert body["bases"][0] == 1468
    assert sum(body["bases"][1:]) == 345


@pytest.mark.parametrize(
    "payload",
    [
        {"question": "not_a_question"},
        {"question": "age"},  # numeric, not a categorical question
        {"question": "gender", "breakdown": "respondent_id"},
        {"question": "gender", "filters": {"region": ["Atlantis"]}},
        {"question": "gender", "filters": {"region; DROP TABLE respondents": ["London"]}},
    ],
)
def test_invalid_requests_are_rejected(client, payload):
    assert client.post("/crosstab", json=payload).status_code == 422


def test_attitude_grid(client):
    body = post(client, "/grid", {"kind": "agree_scale", "breakdown": "eu_ref_vote"})

    assert len(body["rows"]) == 11
    assert body["columns"] == ["Total", "Remain", "Leave", "Did not vote / not stated"]
    assert all(-100 <= value <= 100 for row in body["values"] for value in row)


def test_statement_grid_uses_answered_base(client):
    body = post(client, "/grid", {"kind": "yes_no"})
    total_bases = {row: bases[0] for row, bases in zip(body["rows"], body["bases"], strict=True)}

    assert total_bases["stmt_parents_nearby"] == 1468
    assert total_bases["stmt_multiple_properties"] == 1468 - 882


def test_export_is_filtered_csv(client):
    response = client.post("/export", json={"filters": {"region": ["Wales"]}})
    lines = response.content.decode("utf-8-sig").splitlines()

    assert response.headers["content-type"].startswith("text/csv")
    assert lines[0].startswith("respondent_id,")
    assert len(lines) == 72 + 1
    assert "£" in response.content.decode("utf-8-sig")


def test_data_quality(client):
    body = client.get("/data-quality").json()

    assert body["build"]["clean_rows"] == 1468
    assert {c["status"] for c in body["checks"]} == {"passed", "fixed", "warning"}
