# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Python 3.13+ геоаналитический веб-сервис. Управляется через [uv](https://docs.astral.sh/uv/).

## Commands

```bash
# Установить зависимости
uv sync

# Сгенерировать mock-данные (нужно выполнить один раз перед запуском)
uv run python scripts/generate_mock_data.py

# Запустить сервер (http://localhost:8000)
uv run python main.py

# Добавить зависимость
uv add <package>
```

Swagger UI доступен по адресу http://localhost:8000/docs.

## Tests

```bash
# Все тесты + отчёт покрытия
uv run pytest tests/ -v --cov=app --cov-report=term-missing

# Только один тест
uv run pytest tests/test_api_positive.py::test_health -v

# Только контракт артефактов (не поднимает сервер)
uv run pytest tests/test_artifacts.py -v

# Бенчмарки производительности на реальных данных (медленно, ~60 с)
uv run pytest tests/test_system.py --benchmark-json=benchmark_report.json
```

Тесты требуют наличия Parquet-файлов в `data/` (запустить `generate_mock_data.py` перед первым запуском). `test_system.py::test_benchmark_*` пропускается (`pytest.skip`) если файлы отсутствуют.

Стек: `pytest`, `pytest-cov`, `pytest-benchmark`, `pandera` (dev-зависимости), `httpx` (транзитивно через `fastapi[standard]`). `TestClient` встроен в FastAPI/Starlette.

Структура тестов:
- `tests/conftest.py` — session-scoped `TestClient` (единственная инициализация БД на сессию)
- `tests/test_api_positive.py` — golden path по всем эндпоинтам
- `tests/test_api_negative.py` — контракт ошибок (422, пустой ExplainResponse)
- `tests/test_artifacts.py` — pandera-схемы трёх Parquet-файлов + H3-валидность
- `tests/test_system.py` — gzip-заголовок, бенчмарки лёгкого и полного пути heatmap

## Docker

```bash
# Собрать образ и запустить (данные монтируются из ./data)
docker compose up --build

# Только сборка образа
docker build -t geo-project .
```

Переменные окружения (см. `.env.example`): `DATA_DIR` (путь к папке с Parquet внутри контейнера, дефолт `data`), `HOST` (дефолт `0.0.0.0`), `PORT` (дефолт `8000`). Скопировать `.env.example` → `.env` для переопределения.

## Architecture

Сервис читает Parquet-артефакты через DuckDB и отдаёт их как REST API для визуализации на карте.

**Точка входа:** `main.py` — создаёт FastAPI-приложение через `app.create_app()` и запускает uvicorn (`reload=False`). Хост/порт берутся из `$HOST`/`$PORT`.

**`app/__init__.py`** — фабрика приложения: регистрирует роуты, `GZipMiddleware` (minimum_size=1000), CORS (только GET), StaticFiles, запускает `db.init_db()` через `lifespan`.

**`app/db.py`** — единственное место работы с DuckDB. При старте открывается in-memory соединение, три Parquet-файла загружаются как `TABLE`. Все SQL-запросы идут через глобальный `_conn`, защищённый `threading.Lock` (`_lock`) — FastAPI запускает синхронные эндпоинты в thread pool, поэтому каждый вызов `.execute()` обёрнут в `with _lock`. Функции: `get_categories`, `get_heatmap`, `get_explain`, `get_topk`.

**`app/routes/heatmap.py`** — два эндпоинта:
- `/api/heatmap` — возвращает `list[HexValue]` (только значения, без геометрии). Используется фронтендом при смене категории как лёгкий путь (~4 МБ вместо ~40 МБ).
- `/api/heatmap/geojson` — GeoJSON FeatureCollection. Координаты округлены до 5 знаков (`round(coord, 5)`). Ответ содержит дополнительные поля верхнего уровня `value_min` и `value_max` (вычисляются из данных), которые фронтенд использует для цветовой шкалы. Для `layer=predictions` параметр `category` обязателен.

**`app/routes/explain.py`** — `/api/explain/{h3_index}?category=...&topk=5` возвращает `ExplainResponse` с тремя полями: `prediction` (`PredictionDetail` из predictions по категории, опционально), `growth` (`GrowthDetail` из growth_index), `factors` (топ SHAP-факторов из wide-формата shap_values).

**`app/models.py`** — все Pydantic-схемы: `HexValue`, `ShapFactor`, `TopLocation`, `PredictionDetail`, `GrowthDetail`, `ExplainResponse`, `HealthResponse`, `LayerType`.

**`app/config.py`** — пути к Parquet-файлам (`DATA_DIR / *.parquet`). `DATA_DIR` читается из `$DATA_DIR` (дефолт `"data"`). Константы карты: `MAP_CENTER_LAT=55.75`, `MAP_CENTER_LON=37.62`, `MAP_ZOOM=11`, `H3_RESOLUTION=10`.

**`static/index.html`** — весь фронтенд в одном файле, vanilla JS без сборщика. Зависимости: MapLibre GL JS. Гексагоны рендерятся как нативные MapLibre `fill`-слои. Цвет задаётся через MapLibre `interpolate`-выражение на GPU — JS-цикл по фичам не используется.

Ключевые переменные состояния: `currentLayer`, `currentCategory`, `currentAbortController` (отменяет предыдущий fetch при смене категории), `geometryCache` (кэш геометрии predictions: `{ features, hexIndex: Map<h3_index, Feature> }`), `selectedTopKH3`.

**Логика загрузки данных (две ветки):**
- **Полный путь** — первая загрузка predictions или любой growth_index: `GET /api/heatmap/geojson`, после чего строится `hexIndex` и сохраняется `geometryCache`.
- **Быстрый путь** — смена категории при наличии кэша: `GET /api/heatmap?layer=predictions&category=<cat>`, значения обновляются в `geometryCache.features` за один цикл, min/max пересчитываются на клиенте.

**Карточка топ-20 (`#topk-card`, слева):** отображается только на слое predictions. `loadTopK()` вызывается независимо от `loadHeatmap()` (быстрый запрос `GET /api/topk?category=<cat>&n=20`). `selectTopKItem(h3idx)` подсвечивает строку, вызывает `map.flyTo` к центру гексагона (центр вычисляет `hexCenter()` из `geometryCache.hexIndex` — среднее координат границы) и открывает `onHexClick`. `closeCard()` сбрасывает подсветку топк-списка.

## Data files

`data/` содержит три Parquet-файла (не в git, генерируются скриптом). Реальные колонки:

- `predictions.parquet` — `H3Id, category, mode, DemandPressure, CI, DI, score, has_category` (колонка `has_category` содержит NULL в реальных данных → dtype `object`, не `bool`)
- `shap_values.parquet` — `H3Id, DemandPressure, factor_1..5, value_1..5, sign_1..5, feature_value_1..5` (wide-формат, топ-5 факторов на строку)
- `growth_index.parquet` — `H3Id, cluster, pattern, pattern_color, GrowthIndex`

H3 resolution = 10, центр Москва (55.75, 37.62). Mock-данные генерируются для ~1261 гексагонов (RING_RADIUS=20); реальные данные — ~144 931 гексагон.

Категории: `Аптеки`, `Кафе и рестораны`, `Медицинские товары и услуги`, `Отдых и развлечения`, `Товары повседневного спроса`, плюс агрегат `all`.
