"""Read-only API over the survey warehouse.

    uv run uvicorn api.main:app --reload

Interactive docs at http://localhost:8000/docs
"""

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, Response

from api import queries
from api.models import (
    CountResponse,
    CrosstabRequest,
    CrosstabResponse,
    DataQuality,
    FilterRequest,
    GridRequest,
    GridResponse,
    Question,
)
from api.warehouse import Warehouse, warehouse_path


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.warehouse = Warehouse(warehouse_path())
    yield
    app.state.warehouse.close()


app = FastAPI(
    title="Survey Explorer API",
    description="Crosstabs, summaries and exports from the cleaned survey data.",
    lifespan=lifespan,
)


def get_warehouse(request: Request) -> Warehouse:
    return request.app.state.warehouse


WarehouseDep = Annotated[Warehouse, Depends(get_warehouse)]


@app.exception_handler(queries.InvalidRequest)
def invalid_request(request: Request, exc: queries.InvalidRequest) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/questions", response_model=list[Question])
def list_questions(wh: WarehouseDep):
    return list(wh.questions.values())


@app.post("/count", response_model=CountResponse)
def count(request: FilterRequest, wh: WarehouseDep):
    filters = queries.resolve_filters(wh.questions, request.filters)
    with wh.cursor() as cur:
        return {"respondents": queries.count(cur, filters)}


@app.post("/crosstab", response_model=CrosstabResponse)
def crosstab(request: CrosstabRequest, wh: WarehouseDep):
    question = queries.resolve_question(wh.questions, request.question)
    breakdown = (
        queries.resolve_question(wh.questions, request.breakdown) if request.breakdown else None
    )
    filters = queries.resolve_filters(wh.questions, request.filters)
    with wh.cursor() as cur:
        return queries.crosstab(cur, question, breakdown, filters)


@app.post("/grid", response_model=GridResponse)
def grid(request: GridRequest, wh: WarehouseDep):
    statements = [q for q in wh.questions.values() if q.kind == request.kind]
    breakdown = (
        queries.resolve_question(wh.questions, request.breakdown) if request.breakdown else None
    )
    filters = queries.resolve_filters(wh.questions, request.filters)
    with wh.cursor() as cur:
        return queries.grid(cur, statements, request.kind, breakdown, filters)


@app.post("/export")
def export(request: FilterRequest, wh: WarehouseDep) -> Response:
    filters = queries.resolve_filters(wh.questions, request.filters)
    with wh.cursor() as cur:
        content = queries.export_csv(cur, filters)
    return Response(
        content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="survey_respondents.csv"'},
    )


@app.get("/data-quality", response_model=DataQuality)
def data_quality(wh: WarehouseDep):
    with wh.cursor() as cur:
        return queries.data_quality(cur)
