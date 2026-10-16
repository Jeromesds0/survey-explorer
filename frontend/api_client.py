"""Calls to the survey API. The frontend never reads the database directly."""

import os

import httpx
import streamlit as st

API_URL = os.environ.get("SURVEY_API_URL", "http://localhost:8000")
CACHE_SECONDS = 600


class ApiError(Exception):
    pass


def _request(method: str, path: str, payload: dict | None = None) -> httpx.Response:
    try:
        response = httpx.request(method, f"{API_URL}{path}", json=payload, timeout=30)
    except httpx.TransportError as exc:
        raise ApiError(f"Can't reach the API at {API_URL}. Is it running?") from exc
    if response.is_error:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise ApiError(f"The API returned an error ({response.status_code}): {detail}")
    return response


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def questions() -> list[dict]:
    return _request("GET", "/questions").json()


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def count(filters: dict) -> int:
    return _request("POST", "/count", {"filters": filters}).json()["respondents"]


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def crosstab(question: str, breakdown: str | None, filters: dict) -> dict:
    payload = {"question": question, "breakdown": breakdown, "filters": filters}
    return _request("POST", "/crosstab", payload).json()


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def grid(kind: str, breakdown: str | None, filters: dict) -> dict:
    payload = {"kind": kind, "breakdown": breakdown, "filters": filters}
    return _request("POST", "/grid", payload).json()


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def export_csv(filters: dict) -> bytes:
    return _request("POST", "/export", {"filters": filters}).content


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def data_quality() -> dict:
    return _request("GET", "/data-quality").json()
