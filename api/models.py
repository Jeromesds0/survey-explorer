from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# question id -> answers to keep. Several questions are combined with AND.
Filters = dict[str, list[str]]


class Question(BaseModel):
    id: str
    label: str
    group: str
    kind: str
    base: str
    derived: bool
    options: list[str]


class CrosstabRequest(BaseModel):
    question: str
    breakdown: str | None = None
    filters: Filters = Field(default_factory=dict)


class CrosstabResponse(BaseModel):
    question: str
    breakdown: str | None
    rows: list[str]  # answers to the question, in codebook order
    columns: list[str]  # "Total" followed by the breakdown answers
    bases: list[int]  # respondents in each column
    counts: list[list[int]]
    percents: list[list[float]]  # column percentages
    low_base: int  # columns with fewer respondents than this should be read with caution


class GridRequest(BaseModel):
    kind: Literal["agree_scale", "yes_no"]
    breakdown: str | None = None
    filters: Filters = Field(default_factory=dict)


class GridResponse(BaseModel):
    kind: str
    metric: str
    rows: list[str]  # question ids
    columns: list[str]
    bases: list[list[int]]  # bases differ by question when some weren't asked or answered
    values: list[list[float | None]]
    low_base: int


class FilterRequest(BaseModel):
    filters: Filters = Field(default_factory=dict)


class CountResponse(BaseModel):
    respondents: int


class Check(BaseModel):
    step: str
    status: str
    rows_affected: int
    detail: str


class BuildInfo(BaseModel):
    source_file: str
    source_sha256: str
    raw_rows: int
    clean_rows: int
    built_at: datetime


class DataQuality(BaseModel):
    build: BuildInfo
    checks: list[Check]
