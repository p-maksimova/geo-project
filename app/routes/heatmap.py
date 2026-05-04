from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
import h3
from app import db
from app.models import HexValue, LayerType

router = APIRouter()


@router.get("/heatmap", response_model=list[HexValue])
def heatmap(
    layer: LayerType = Query("predictions"),
    category: str | None = Query(None),
):
    if layer == "predictions" and not category:
        raise HTTPException(status_code=422, detail="category is required for layer=predictions")
    return db.get_heatmap(layer, category)


@router.get("/heatmap/geojson")
def heatmap_geojson(
    layer: LayerType = Query("predictions"),
    category: str | None = Query(None),
):
    if layer == "predictions" and not category:
        raise HTTPException(status_code=422, detail="category is required for layer=predictions")
    rows = db.get_heatmap(layer, category)

    values = [row.value for row in rows]
    val_min = min(values) if values else 0.0
    val_max = max(values) if values else 1.0

    features = []
    for row in rows:
        # h3-python: cellToBoundary возвращает [(lat, lng), ...] — меняем на [lng, lat] для GeoJSON
        # 5 знаков после запятой (~1 м точности) достаточно для карты и вдвое уменьшает JSON
        boundary = [[round(lng, 5), round(lat, 5)] for lat, lng in h3.cell_to_boundary(row.h3_index)]
        boundary.append(boundary[0])  # замкнуть кольцо
        props: dict = {"h3_index": row.h3_index, "value": round(row.value, 4)}
        if row.pattern_color is not None:
            props["pattern_color"] = row.pattern_color
        if row.pattern is not None:
            props["pattern"] = row.pattern
        if row.cluster is not None:
            props["cluster"] = row.cluster
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [boundary]},
            "properties": props,
        })
    return JSONResponse({
        "type": "FeatureCollection",
        "value_min": round(val_min, 4),
        "value_max": round(val_max, 4),
        "features": features,
    })
