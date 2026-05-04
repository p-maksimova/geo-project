from fastapi import APIRouter, Query
from app import db
from app.models import TopLocation

router = APIRouter()


@router.get("/topk", response_model=list[TopLocation])
def topk(category: str = Query(...), n: int = Query(10, ge=1, le=100)):
    return db.get_topk(category, n)
