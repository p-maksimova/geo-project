"""Негативные API-тесты: фиксируем контракт ошибочных запросов."""


def test_heatmap_predictions_without_category_returns_422(client):
    r = client.get("/api/heatmap?layer=predictions")
    assert r.status_code == 422


def test_explain_invalid_h3_returns_null_fields(client):
    r = client.get("/api/explain/INVALID_H3_INDEX?category=Аптеки")
    assert r.status_code == 200
    data = r.json()
    assert data["prediction"] is None
    assert data["growth"] is None
    assert data["factors"] == []
