"""Generate synthetic parquet data files for development and testing.

Schema mirrors the real data (column names, value ranges, distributions).
Real data has ~144 931 hexes; mock uses RING_RADIUS=20 (~1 261 hexes) by default.
Increase RING_RADIUS to approach production scale.
"""

import sys
from pathlib import Path

import h3
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.config import (
    GROWTH_INDEX_PATH,
    H3_RESOLUTION,
    MAP_CENTER_LAT,
    MAP_CENTER_LON,
    PREDICTIONS_PATH,
    SHAP_VALUES_PATH,
)

# Категории из реальных данных (включая агрегированную 'all')
REAL_CATEGORIES = [
    "Аптеки",
    "Кафе и рестораны",
    "Медицинские товары и услуги",
    "Отдых и развлечения",
    "Товары повседневного спроса",
]

# Паттерны роста из реальных данных
PATTERNS = [
    (-1, "Нестабильный рост", "#f5c518"),
    (0,  "Восстановление",    "#85c785"),
    (1,  "Устойчивый рост",   "#2d9e2d"),
]
# Вероятности паттернов (из реальных данных: -1→60%, 0→15%, 1→25%)
PATTERN_WEIGHTS = [0.60, 0.15, 0.25]

# Реальные названия факторов SHAP (105 штук, используем подмножество)
SHAP_FEATURES = [
    "osm_amenity_food__amenity__cnt_cafe",
    "osm_amenity_food__amenity__cnt_restaurant",
    "osm_amenity_food__amenity__cnt_fast_food",
    "osm_amenity_food__amenity__cnt_bar",
    "osm_amenity_healthcare__amenity__cnt_pharmacy",
    "osm_amenity_healthcare__amenity__cnt_clinic",
    "osm_amenity_healthcare__amenity__cnt_hospital",
    "osm_amenity_healthcare__amenity__cnt_doctors",
    "osm_amenity_shopping__shop__cnt_supermarket",
    "osm_amenity_shopping__shop__cnt_mall",
    "osm_amenity_shopping__shop__cnt_department_store",
    "osm_amenity_social__amenity__cnt_bank",
    "osm_amenity_social__amenity__cnt_post_office",
    "osm_amenity_social__amenity__cnt_social_facility",
    "osm_amenity_education__amenity__cnt_school",
    "osm_amenity_education__amenity__cnt_kindergarten",
    "osm_leisure_parks__leisure__cnt_playground",
    "osm_leisure_parks__leisure__cnt_sports_centre",
    "osm_office__osm_id__count",
    "osm_real_estate__osm_id__count",
    "osm_transport_bus__osm_id__count",
    "transform__transport_metro",
    "transform__cian_flat_floors_total",
    "transform__cian_flat_year_built",
    "transform__cian_flat_offer_category_flat",
    "transform__cian_flat_offer_category_room",
    "transform__commercial_floors_total",
    "transform__commercial_offer_category_office",
    "cian_flat_sale__price_per_m2__mean",
    "cian_flat_sale__price__median",
    "cian_flat_rent_long__price__median",
    "cian_commercial_rent__price_per_m2__median",
    "cian_commercial_rent__id__count",
    "cian_newbuild__id__count",
    "cian_flat_rent_daily__id__count",
    "mos_ru_2542__YardArea__sum",
    "lag1__osm_amenity_food__amenity__cnt_cafe",
    "lag1__osm_amenity_food__amenity__cnt_restaurant",
    "lag1__osm_amenity_healthcare__amenity__cnt_pharmacy",
    "lag1__osm_amenity_shopping__shop__cnt_supermarket",
    "lag1__osm_amenity_social__amenity__cnt_bank",
    "lag1__osm_real_estate__osm_id__count",
    "lag1__osm_transport_bus__osm_id__count",
    "lag1__transform__transport_metro",
    "lag1__cian_flat_sale__price_per_m2__mean",
    "lag1__cian_flat_rent_long__price__median",
    "lag2__osm_amenity_food__amenity__cnt_restaurant",
    "lag2__osm_amenity_healthcare__amenity__cnt_pharmacy",
    "lag2__osm_amenity_shopping__shop__cnt_supermarket",
    "lag2__osm_amenity_social__amenity__cnt_bank",
]

RING_RADIUS = 20  # ~1 261 гексагонов; для полного масштаба используйте ~213
rng = np.random.default_rng(42)


def get_hex_grid(lat: float, lon: float, resolution: int, rings: int) -> list[str]:
    center = h3.latlng_to_cell(lat, lon, resolution)
    return list(h3.grid_disk(center, rings))


def make_predictions(hexes: list[str]) -> pd.DataFrame:
    """Генерирует predictions с теми же колонками и диапазонами, что в реальных данных."""
    rows = []
    n = len(hexes)

    # Сначала создаём строки для каждой реальной категории
    for category in REAL_CATEGORIES:
        demand = rng.uniform(0.693, 188.4, n)
        score = demand  # в реальных данных score ≈ DemandPressure
        ci = rng.choice([1.0, 1.5], n)
        di = rng.choice([2 / 3, 1.0], n)
        mode = rng.choice(["saturation", "deficit"], n, p=[0.6, 0.4])
        has_cat = rng.choice([True, False], n, p=[0.016, 0.984])

        for i, h3_idx in enumerate(hexes):
            rows.append({
                "H3Id": h3_idx,
                "category": category,
                "mode": mode[i],
                "DemandPressure": float(demand[i]),
                "CI": float(ci[i]),
                "DI": float(di[i]),
                "score": float(score[i]),
                "has_category": bool(has_cat[i]),
            })

    # Агрегированная строка 'all' — среднее по категориям, mode/has_category = None
    cat_df = pd.DataFrame(rows)
    agg = (
        cat_df.groupby("H3Id")[["DemandPressure", "CI", "DI", "score"]]
        .mean()
        .reset_index()
    )
    agg["category"] = "all"
    agg["mode"] = None
    agg["has_category"] = None

    return pd.concat([cat_df, agg], ignore_index=True)


def make_shap_values(hexes: list[str], predictions_df: pd.DataFrame) -> pd.DataFrame:
    """Генерирует SHAP-факторы в wide-формате (factor_1..5), как в реальных данных."""
    n = len(hexes)
    demand_map = predictions_df[predictions_df["category"] == "all"].set_index("H3Id")["DemandPressure"]

    rows = []
    n_features = len(SHAP_FEATURES)
    for h3_idx in hexes:
        shap_vals = rng.normal(0, 3.0, n_features)
        order = np.argsort(np.abs(shap_vals))[::-1][:5]

        row: dict = {"H3Id": h3_idx, "DemandPressure": float(demand_map.get(h3_idx, 1.0))}
        for rank, fi in enumerate(order, start=1):
            sv = float(shap_vals[fi])
            fv = float(rng.uniform(0, 10))
            row[f"factor_{rank}"] = SHAP_FEATURES[fi]
            row[f"value_{rank}"] = sv
            row[f"sign_{rank}"] = "+" if sv >= 0 else "-"
            row[f"feature_value_{rank}"] = fv
        rows.append(row)

    return pd.DataFrame(rows)


def make_growth_index(hexes: list[str]) -> pd.DataFrame:
    """Генерирует индекс роста с теми же колонками и диапазонами, что в реальных данных."""
    n = len(hexes)
    pattern_indices = rng.choice(len(PATTERNS), n, p=PATTERN_WEIGHTS)
    gi_values = rng.uniform(-14.2, 16.1, n)

    rows = []
    for i, h3_idx in enumerate(hexes):
        cluster, pattern, color = PATTERNS[pattern_indices[i]]
        rows.append({
            "H3Id": h3_idx,
            "cluster": int(cluster),
            "pattern": pattern,
            "pattern_color": color,
            "GrowthIndex": float(gi_values[i]),
        })
    return pd.DataFrame(rows)


def main() -> None:
    Path("data").mkdir(exist_ok=True)
    hexes = get_hex_grid(MAP_CENTER_LAT, MAP_CENTER_LON, H3_RESOLUTION, RING_RADIUS)
    print(f"Generating {len(hexes)} hexes (resolution={H3_RESOLUTION}, rings={RING_RADIUS})")
    print(f"(real data: ~144 931 hexes)")

    predictions = make_predictions(hexes)
    predictions.to_parquet(PREDICTIONS_PATH, index=False)
    print(f"  predictions.parquet: {len(predictions)} strok -> {PREDICTIONS_PATH}")

    shap_values = make_shap_values(hexes, predictions)
    shap_values.to_parquet(SHAP_VALUES_PATH, index=False)
    print(f"  shap_values.parquet: {len(shap_values)} strok -> {SHAP_VALUES_PATH}")

    growth_index = make_growth_index(hexes)
    growth_index.to_parquet(GROWTH_INDEX_PATH, index=False)
    print(f"  growth_index.parquet: {len(growth_index)} strok -> {GROWTH_INDEX_PATH}")

    print("Done.")


if __name__ == "__main__":
    main()
