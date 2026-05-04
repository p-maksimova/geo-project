from fastapi import APIRouter, Query
from app import db
from app.models import ExplainResponse

router = APIRouter()


@router.get("/explain/{h3_index}", response_model=ExplainResponse)
def explain(
    h3_index: str,
    topk: int = Query(5, ge=1, le=20),
    category: str | None = Query(None),
):
    return db.get_explain(h3_index, topk, category)
