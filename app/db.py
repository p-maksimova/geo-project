import threading
import duckdb
from app.config import PREDICTIONS_PATH, SHAP_VALUES_PATH, GROWTH_INDEX_PATH
from app.models import HexValue, ShapFactor, TopLocation, ExplainResponse, PredictionDetail, GrowthDetail

_conn: duckdb.DuckDBPyConnection | None = None
_lock = threading.Lock()


def init_db() -> None:
    global _conn
    _conn = duckdb.connect(":memory:")
    _conn.execute(f"CREATE TABLE predictions AS SELECT * FROM read_parquet('{PREDICTIONS_PATH}')")
    _conn.execute(f"CREATE TABLE shap_values AS SELECT * FROM read_parquet('{SHAP_VALUES_PATH}')")
    _conn.execute(f"CREATE TABLE growth_index AS SELECT * FROM read_parquet('{GROWTH_INDEX_PATH}')")


def get_db() -> duckdb.DuckDBPyConnection:
    if _conn is None:
        raise RuntimeError("Database not initialized")
    return _conn


def get_categories() -> list[str]:
    with _lock:
        rows = get_db().execute("SELECT DISTINCT category FROM predictions ORDER BY category").fetchall()
    return [r[0] for r in rows]


def get_heatmap(layer: str, category: str | None = None) -> list[HexValue]:
    if layer == "predictions":
        with _lock:
            rows = get_db().execute(
                "SELECT H3Id, score AS value FROM predictions WHERE category = ? ORDER BY H3Id",
                [category or "all"],
            ).fetchall()
        return [HexValue(h3_index=r[0], value=r[1]) for r in rows]
    else:
        with _lock:
            rows = get_db().execute(
                "SELECT H3Id, GrowthIndex, pattern_color, pattern, cluster FROM growth_index ORDER BY H3Id"
            ).fetchall()
        return [
            HexValue(h3_index=r[0], value=r[1], pattern_color=r[2], pattern=r[3], cluster=r[4])
            for r in rows
        ]


def get_explain(h3_index: str, topk: int = 5, category: str | None = None) -> ExplainResponse:
    with _lock:
        gi_row = get_db().execute(
            "SELECT GrowthIndex, cluster, pattern, pattern_color FROM growth_index WHERE H3Id = ? LIMIT 1",
            [h3_index],
        ).fetchone()

    growth = GrowthDetail(
        value=float(gi_row[0]),
        cluster=int(gi_row[1]),
        pattern=gi_row[2],
        pattern_color=gi_row[3],
    ) if gi_row else None

    prediction = None
    if category:
        with _lock:
            pred_row = get_db().execute(
                "SELECT score, mode, DemandPressure, CI, DI, has_category FROM predictions WHERE H3Id = ? AND category = ? LIMIT 1",
                [h3_index, category],
            ).fetchone()
        if pred_row:
            prediction = PredictionDetail(
                score=float(pred_row[0]) if pred_row[0] is not None else 0.0,
                mode=pred_row[1],
                demand_pressure=float(pred_row[2]) if pred_row[2] is not None else 0.0,
                ci=float(pred_row[3]) if pred_row[3] is not None else 0.0,
                di=float(pred_row[4]) if pred_row[4] is not None else 0.0,
                has_category=bool(pred_row[5]),
            )

    with _lock:
        shap_row = get_db().execute(
            """SELECT factor_1, value_1, sign_1, feature_value_1,
                      factor_2, value_2, sign_2, feature_value_2,
                      factor_3, value_3, sign_3, feature_value_3,
                      factor_4, value_4, sign_4, feature_value_4,
                      factor_5, value_5, sign_5, feature_value_5
               FROM shap_values WHERE H3Id = ? LIMIT 1""",
            [h3_index],
        ).fetchone()

    factors: list[ShapFactor] = []
    if shap_row:
        for i in range(5):
            base = i * 4
            factor_name = shap_row[base]
            if factor_name:
                factors.append(ShapFactor(
                    feature=factor_name,
                    shap_value=float(shap_row[base + 1]),
                    sign=shap_row[base + 2],
                    feature_value=float(shap_row[base + 3]) if shap_row[base + 3] is not None else None,
                ))
        factors.sort(key=lambda f: abs(f.shap_value), reverse=True)
        factors = factors[:topk]

    return ExplainResponse(prediction=prediction, growth=growth, factors=factors)


def get_topk(category: str, n: int = 10) -> list[TopLocation]:
    with _lock:
        rows = get_db().execute(
            """SELECT H3Id, score, ROW_NUMBER() OVER (ORDER BY score DESC) AS rank
               FROM predictions WHERE category = ?
               ORDER BY score DESC LIMIT ?""",
            [category, n],
        ).fetchall()
    return [TopLocation(h3_index=r[0], value=r[1], rank=r[2]) for r in rows]
