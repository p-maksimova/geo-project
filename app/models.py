from pydantic import BaseModel
from typing import Literal


class HexValue(BaseModel):
    h3_index: str
    value: float
    pattern_color: str | None = None
    pattern: str | None = None
    cluster: int | None = None


class ShapFactor(BaseModel):
    feature: str
    shap_value: float
    sign: str
    feature_value: float | None


class TopLocation(BaseModel):
    h3_index: str
    value: float
    rank: int


class PredictionDetail(BaseModel):
    score: float
    mode: str | None
    demand_pressure: float
    ci: float
    di: float
    has_category: bool


class GrowthDetail(BaseModel):
    value: float
    cluster: int
    pattern: str
    pattern_color: str


class ExplainResponse(BaseModel):
    prediction: PredictionDetail | None
    growth: GrowthDetail | None
    factors: list[ShapFactor]


class HealthResponse(BaseModel):
    status: str


LayerType = Literal["predictions", "growth_index"]
