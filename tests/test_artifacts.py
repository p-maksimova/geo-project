"""Контракт Parquet-артефактов: схема, типы, целостность данных."""
import pytest
import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Column, DataFrameSchema
import h3
from app.config import PREDICTIONS_PATH, SHAP_VALUES_PATH, GROWTH_INDEX_PATH


def _require_file(path):
    if not path.exists():
        pytest.skip(f"Файл не найден: {path}")


# --- Схемы ---

predictions_schema = DataFrameSchema(
    {
        "H3Id": Column(str, nullable=False),
        "category": Column(str, nullable=False),
        "score": Column(float, nullable=False),
        "mode": Column(str, nullable=True),
        "DemandPressure": Column(float, nullable=True),
        "CI": Column(float, nullable=True),
        "DI": Column(float, nullable=True),
        "has_category": Column(object, nullable=True),  # bool+NULL → object в pandas
    }
)

shap_schema = DataFrameSchema(
    {
        "H3Id": Column(str, nullable=False),
        **{
            col: Column(dtype, nullable=True)
            for i in range(1, 6)
            for col, dtype in [
                (f"factor_{i}", str),
                (f"value_{i}", float),
                (f"sign_{i}", str),
                (f"feature_value_{i}", float),
            ]
        },
    }
)

growth_schema = DataFrameSchema(
    {
        "H3Id": Column(str, nullable=False),
        "GrowthIndex": Column(float, nullable=False),
        "cluster": Column(int, nullable=False),
        "pattern": Column(str, nullable=False),
        "pattern_color": Column(str, nullable=False),
    }
)


# --- Тесты ---

def test_predictions_schema():
    _require_file(PREDICTIONS_PATH)
    df = pd.read_parquet(PREDICTIONS_PATH)
    predictions_schema.validate(df)


def test_shap_values_schema():
    _require_file(SHAP_VALUES_PATH)
    df = pd.read_parquet(SHAP_VALUES_PATH)
    shap_schema.validate(df)


def test_growth_index_schema():
    _require_file(GROWTH_INDEX_PATH)
    df = pd.read_parquet(GROWTH_INDEX_PATH)
    growth_schema.validate(df)


def test_h3ids_are_valid():
    for path in (PREDICTIONS_PATH, SHAP_VALUES_PATH, GROWTH_INDEX_PATH):
        _require_file(path)
    for path in (PREDICTIONS_PATH, SHAP_VALUES_PATH, GROWTH_INDEX_PATH):
        df = pd.read_parquet(path, columns=["H3Id"])
        invalid = df["H3Id"][~df["H3Id"].apply(h3.is_valid_cell)]
        assert len(invalid) == 0, f"{path.name}: невалидные H3Id: {invalid.head().tolist()}"


def test_no_nulls_in_key_columns():
    _require_file(PREDICTIONS_PATH)
    _require_file(GROWTH_INDEX_PATH)
    pred = pd.read_parquet(PREDICTIONS_PATH, columns=["H3Id", "score"])
    assert pred["H3Id"].notna().all(), "predictions.parquet: NULL в H3Id"
    assert pred["score"].notna().all(), "predictions.parquet: NULL в score"

    gi = pd.read_parquet(GROWTH_INDEX_PATH, columns=["H3Id", "GrowthIndex"])
    assert gi["H3Id"].notna().all(), "growth_index.parquet: NULL в H3Id"
    assert gi["GrowthIndex"].notna().all(), "growth_index.parquet: NULL в GrowthIndex"
