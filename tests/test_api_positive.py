"""Позитивные API-тесты: проверяем, что golden path работает корректно."""


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_categories_returns_list(client):
    r = client.get("/api/categories")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert all(isinstance(c, str) for c in data)


def test_heatmap_growth_index(client):
    r = client.get("/api/heatmap?layer=growth_index")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0
    item = data[0]
    assert "h3_index" in item
    assert "value" in item


def test_heatmap_geojson_predictions(client):
    r = client.get("/api/heatmap/geojson?layer=predictions&category=Аптеки")
    assert r.status_code == 200
    data = r.json()
    assert data["type"] == "FeatureCollection"
    assert "value_min" in data
    assert "value_max" in data
    assert isinstance(data["features"], list)
    assert len(data["features"]) > 0
    feat = data["features"][0]
    assert feat["geometry"]["type"] == "Polygon"
    assert "h3_index" in feat["properties"]
    assert "value" in feat["properties"]


def test_topk_returns_ranked_list(client):
    r = client.get("/api/topk?category=Аптеки&n=5")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 5
    ranks = [item["rank"] for item in data]
    assert ranks == list(range(1, 6))
