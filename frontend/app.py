"""Streamlit app for exploring the survey.

    uv run streamlit run frontend/app.py

Expects the API to be running (SURVEY_API_URL, default http://localhost:8000).
"""

import streamlit as st

import api_client
import views

FILTER_QUESTIONS = [
    "gender",
    "age_band",
    "nation",
    "region",
    "income_group",
    "work_status",
    "political_interest",
    "eu_ref_vote",
    "vote_intention",
]

st.set_page_config(page_title="Survey Explorer", page_icon="📊", layout="wide")

# Charts with many columns can be wider than the page on small screens: scroll them sideways
# instead of letting them run off the edge
st.html("<style>div:has(> [data-testid='stVegaLiteChart']) { overflow-x: auto; }</style>")

try:
    questions = {q["id"]: q for q in api_client.questions()}
except api_client.ApiError as exc:
    st.error(str(exc))
    st.info("Start the API and the app together with `uv run start.py`.")
    st.stop()


def clear_filters() -> None:
    for question_id in FILTER_QUESTIONS:
        st.session_state[f"filter_{question_id}"] = []


with st.sidebar:
    st.header("Filters")
    filters = {}
    for question_id in FILTER_QUESTIONS:
        question = questions[question_id]
        selected = st.multiselect(
            question["label"], question["options"], key=f"filter_{question_id}", placeholder="All"
        )
        if selected:
            filters[question_id] = selected

    respondents = api_client.count(filters)
    st.metric("Respondents matching filters", f"{respondents:,}")
    if respondents < 50:
        st.warning("Fewer than 50 respondents. Results will be unreliable.")
    st.button("Clear filters", on_click=clear_filters, disabled=not filters)

st.session_state["filters"] = filters

page = st.navigation(
    [
        st.Page(views.crosstab_page, title="Crosstabs", icon="📊", default=True),
        st.Page(views.grid_page, title="Attitudes and statements", icon="🧭"),
        st.Page(views.quality_page, title="Data quality", icon="🧪"),
        st.Page(views.data_page, title="Codebook and export", icon="📁"),
    ]
)
try:
    page.run()
except api_client.ApiError as exc:
    st.error(str(exc))
