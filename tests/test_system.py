"""Системные тесты: middleware и производительность на реальных данных."""
import pytest
from fastapi.testclient import TestClient
from app import create_app
from app.config import PREDICTIONS_PATH


def _require_real_data():
    if not PREDICTIONS_PATH.exists():
        pytest.skip("Реальные данные не найдены")


def test_gzip_compression(client):
    r = client.get(
        "/api/heatmap/geojson?layer=predictions&category=Аптеки",
        headers={"Accept-Encoding": "gzip"},
    )
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"


def test_benchmark_geojson_full_path(benchmark):
    _require_real_data()
    app = create_app()
    with TestClient(app) as c:
        result = benchmark(
            c.get,
            "/api/heatmap/geojson?layer=predictions&category=Аптеки",
        )
    assert result.status_code == 200


def test_benchmark_heatmap_fast_path(benchmark):
    _require_real_data()
    app = create_app()
    with TestClient(app) as c:
        result = benchmark(
            c.get,
            "/api/heatmap?layer=predictions&category=Аптеки",
        )
    assert result.status_code == 200
