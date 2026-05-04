from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from app import db
from app.routes import categories, heatmap, explain, topk, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Geo Analytics API",
        description="Геоаналитический сервис: тепловые карты и SHAP-объяснения по H3-гексагонам",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    for router in [categories.router, heatmap.router, explain.router, topk.router, health.router]:
        app.include_router(router, prefix="/api")

    app.mount("/", StaticFiles(directory="static", html=True), name="static")

    return app
