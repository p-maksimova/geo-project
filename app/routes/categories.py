from fastapi import APIRouter
from app import db

router = APIRouter()


@router.get("/categories", response_model=list[str])
def categories():
    return db.get_categories()
