import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
PREDICTIONS_PATH = DATA_DIR / "predictions.parquet"
SHAP_VALUES_PATH = DATA_DIR / "shap_values.parquet"
GROWTH_INDEX_PATH = DATA_DIR / "growth_index.parquet"

MAP_CENTER_LAT = 55.75
MAP_CENTER_LON = 37.62
MAP_ZOOM = 11
H3_RESOLUTION = 10
