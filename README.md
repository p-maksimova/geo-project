# Геоаналитический сервис

Веб-сервис для визуализации предсказаний ML-модели и индекса роста бизнеса по гексагональной сетке H3 над картой Москвы. Реализует сценарий: выбор категории бизнеса → тепловая карта + топ-20 лучших локаций → выбор или клик по гексагону → карточка с полной аналитикой и SHAP-объяснением.

## Стек

| Слой | Технологии |
|---|---|
| API | FastAPI + Uvicorn |
| Данные | DuckDB (in-process), Parquet |
| Карта | MapLibre GL JS 4.7 |
| Гексагональная сетка | H3 (resolution 10, Python) |

## Быстрый старт

**Локально (uv):**

```bash
uv sync
uv run python scripts/generate_mock_data.py  # один раз
uv run python main.py
```

**Docker:**

```bash
uv run python scripts/generate_mock_data.py  # генерирует ./data на хосте
docker compose up --build
```

- Приложение: http://localhost:8000
- Swagger UI: http://localhost:8000/docs

Переменные окружения (см. `.env.example`): `DATA_DIR` (путь к папке с Parquet, дефолт `data`), `HOST` (дефолт `0.0.0.0`), `PORT` (дефолт `8000`).

## Пользовательский сценарий

**Слой «Предсказания»**

1. Выбрать категорию бизнеса в выпадающем списке: Аптеки, Кафе и рестораны, Медицинские товары и услуги, Отдых и развлечения, Товары повседневного спроса, или агрегат `all`.
2. Карта окрашивает гексагоны по `score` от синего (низкое) к красному (высокое).
3. Слева появляется **карточка «Топ 20 локаций»** — рейтинговый список лучших гексагонов по `score`. Клик на строку перемещает карту к гексагону и открывает карточку детализации.
4. Клик по гексагону на карте — карточка показывает:
   - для `all`: экономическую активность (score)
   - для конкретной категории: экономическую активность (`DemandPressure`), экономическую активность с учётом CI/DI (`score`), значения CI/DI, наличие категории
   - топ-5 SHAP-факторов с горизонтальными барами

**Слой «Индекс роста»**

Два подрежима через кнопки-переключатели:
- **GrowthIndex** — градиентная шкала агрегированного индекса роста.
- **Паттерн** — заливка по кластеру: Нестабильный рост (жёлтый), Восстановление (светло-зелёный), Устойчивый рост (зелёный).

Клик по гексагону — карточка показывает значение GrowthIndex и паттерн кластера.

## API

| Метод | Путь | Параметры | Описание |
|---|---|---|---|
| GET | `/api/categories` | — | Список категорий из `predictions` |
| GET | `/api/heatmap` | `layer`, `category`* | Массив `{h3_index, value, …}` без геометрии |
| GET | `/api/heatmap/geojson` | `layer`, `category`* | GeoJSON FeatureCollection с полигонами + `value_min`, `value_max` |
| GET | `/api/explain/{h3_index}` | `category`, `topk=5` | Оценка, индекс роста, SHAP-факторы |
| GET | `/api/topk` | `category`, `n=20` (max 100) | Топ-N локаций по `score` |
| GET | `/api/health` | — | `{"status": "ok"}` |

\* `category` обязателен при `layer=predictions`.

`/api/heatmap/geojson` вычисляет полигоны на сервере через `h3.cell_to_boundary` (координаты округлены до 5 знаков) и добавляет в корень ответа `value_min`/`value_max` для цветовой шкалы. Все ответы сжимаются gzip.

`/api/explain` возвращает:
```json
{
  "prediction": { "score": 42.1, "mode": "deficit", "demand_pressure": 38.5, "ci": 1.5, "di": 0.67, "has_category": true },
  "growth":     { "value": 3.7, "cluster": 1, "pattern": "Устойчивый рост", "pattern_color": "#2d9e2d" },
  "factors":    [{ "feature": "osm_amenity_food__...", "shap_value": 1.23, "sign": "+", "feature_value": 4.5 }, …]
}
```

## Данные

Три Parquet-файла в `data/` (не в git, генерируются скриптом):

| Файл | Ключевые колонки |
|---|---|
| `predictions.parquet` | `H3Id, category, score, mode, DemandPressure, CI, DI, has_category` |
| `shap_values.parquet` | `H3Id, factor_1..5, value_1..5, sign_1..5, feature_value_1..5` (wide-формат) |
| `growth_index.parquet` | `H3Id, GrowthIndex, cluster, pattern, pattern_color` |

DuckDB загружает файлы как таблицы в памяти при старте. Доступ к единственному соединению сериализован через `threading.Lock` — FastAPI выполняет синхронные эндпоинты в thread pool.

**Mock vs. реальные данные:** скрипт генерирует ~1 261 гексагон (RING_RADIUS=20); реальные данные содержат ~144 931 гексагон. Для приближения к боевому масштабу увеличьте `RING_RADIUS` в `scripts/generate_mock_data.py`.

## Структура проекта

```
geo-project/
├── main.py                      # Точка входа: uvicorn + create_app()
├── app/
│   ├── __init__.py              # Фабрика приложения, GZipMiddleware, lifespan
│   ├── config.py                # Пути к Parquet-файлам, параметры карты
│   ├── db.py                    # DuckDB: инициализация, threading.Lock, все SQL-запросы
│   ├── models.py                # Pydantic-схемы
│   └── routes/
│       ├── heatmap.py           # /api/heatmap, /api/heatmap/geojson
│       ├── explain.py           # /api/explain/{h3_index}
│       ├── categories.py        # /api/categories
│       ├── topk.py              # /api/topk
│       └── health.py            # /api/health
├── static/
│   └── index.html               # Весь фронтенд (vanilla JS, MapLibre GL JS)
├── scripts/
│   └── generate_mock_data.py    # Генератор синтетических Parquet-данных
├── Dockerfile                   # Multi-stage build (builder + runtime)
├── docker-compose.yml           # Один сервис, volume ./data:/app/data
├── .env.example                 # Контракт переменных окружения
└── data/                        # Parquet-артефакты (не в git)
```
