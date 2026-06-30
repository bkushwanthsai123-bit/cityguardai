# Smart City: Illegal Garbage Dumping Detection

End-to-end system that detects illegal garbage dumping in street imagery, turns
each detection into a structured, actionable **incident report** using a local
LLM, persists it, and surfaces everything on an interactive map dashboard for
city operations teams.

**Stack:** YOLOv8 (Ultralytics) for detection · local Ollama LLM (`llama3.2:1b`,
a lightweight CPU-friendly 1B model) + deterministic rules for incident
reasoning · FastAPI REST API · SQLite
(Postgres-swappable) · a primary **Next.js "CityGuard AI" dashboard** (App
Router, React 19, Tailwind v4) and an alternate **Streamlit** app, both with
map, filters, and analytics.

---

## Overview

Illegal dumping is expensive and slow to act on because reports are unstructured
and uncategorized. This project automates the loop:

1. A field image (citizen app, CCTV frame, patrol upload) is sent to the API.
2. **YOLOv8** detects waste objects across 5 classes.
3. The **LLM layer** drafts a human-readable incident report; **deterministic
   rules** own all the numbers (severity score, band, priority, department,
   SLA) so output is always valid and reproducible.
4. The incident is stored in SQLite and exposed over REST.
5. Two clients consume that REST API: the primary **Next.js dashboard**
   (`frontend/`) and the alternate **Streamlit app** (`dashboard/`), each
   plotting hotspots on a map with filtering and analytics for dispatch and
   trend monitoring.

### Detection classes

`Glass`, `Metal`, `Paper`, `Plastic`, `Waste`

### Severity, priority & routing (deterministic)

- **Severity score (0-100):** `min(100, round(100 * Σ(class_weight * bbox_area_fraction) + 5*count_bonus))`
  with class weights `Waste=1.0, Glass=0.8, Metal=0.6, Plastic=0.6, Paper=0.4`
  and `count_bonus = min(detection_count, 5)`.
- **Bands:** 0-25 low · 26-50 medium · 51-75 high · 76-100 critical.
- **Priority:** critical->P1, high->P2, medium->P3, low->P4.
- **SLA hours:** P1=4, P2=12, P3=24, P4=72.
- **Department routing:** `Waste`/`Glass`/`Metal` -> Solid Waste Management;
  `Plastic` -> Sanitation Department; `Paper` -> Street Cleaning / Public Health.
  Mixed detections route to the highest-weight class present.

---

## Architecture

```
Image -> FastAPI /detect -> YOLOv8 Detector -> LLM layer (Ollama + rules)
      -> SQLite -> REST API -+-> Next.js dashboard (primary)
                             +-> Streamlit dashboard (alternate)
```

The LLM is constrained: it writes the prose (title, description, recommended
action) while deterministic rules compute and clamp every numeric/categorical
field. If Ollama is unreachable the system falls back entirely to rules, so it
**always** produces a valid report. The API enables CORS (all origins) and
serves uploaded detection images as static files under `/uploads`, so either
frontend can render them directly. See [`docs/architecture.md`](docs/architecture.md)
for the full Mermaid diagram and data-flow narrative.

---

## Features

- YOLOv8 detector with graceful fallback to `yolov8n.pt` if trained weights are
  absent (the app still boots).
- Single and batch image detection endpoints.
- LLM-authored incident reports with deterministic, validated scoring.
- Vendor-agnostic LLM layer via an `AIProvider` abstraction (Ollama default).
- Full REST API with filtering, analytics summary, and geospatial hotspots.
- CORS enabled and uploaded images served from `/uploads` for browser clients.
- Primary Next.js "CityGuard AI" dashboard plus an alternate Streamlit app:
  map view, multi-field filters, analytics, and a live detection page.
- SQLite by default, Postgres-swappable through a single `DB_URL`.
- One-command local run and a Dockerized 3-service stack.

---

## Quickstart

> Tested on macOS Apple Silicon (M-series) and Linux. **Requires Python 3.10+**
> (3.12 recommended): the code uses `from __future__ import annotations` with
> PEP 604 `X | Y` unions that Python 3.9 cannot evaluate at runtime. On macOS
> Apple Silicon, install a supported interpreter via Homebrew: `brew install
> python@3.12`. The Node.js frontend is optional and covered in its own section
> below.

### Option A - with Ollama (full LLM reports)

```bash
# 1. Clone and enter
cd smart-city-garbage

# 2. Virtual environment + dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Config
cp .env.example .env

# 4. (Optional) pull the local LLM - install Ollama first from https://ollama.com
ollama pull llama3.2:1b

# 5. Seed demo incidents so the dashboard is populated
python -m app.seed

# 6. Run the API (Swagger UI at http://localhost:8000/docs)
uvicorn app.main:app --reload

# 7. In a second terminal (venv activated) run the dashboard
streamlit run dashboard/app.py
```

### Option B - without Ollama (deterministic rules only)

Skip step 4. The LLM layer detects that Ollama is unreachable and falls back to
`rules.build_report()`, producing fully valid incidents with rule-generated
text. Everything else is identical.

### Frontend (Next.js dashboard)

The primary UI is the "CityGuard AI" dashboard in `frontend/` (Next.js 16 App
Router, React 19, TypeScript, Tailwind v4). With the API running on port 8000:

```bash
cd frontend
npm install
npm run dev      # serves http://localhost:3000
```

It expects the backend at `http://localhost:8000` by default. To point at a
different backend, set `NEXT_PUBLIC_API_URL` (e.g. in `frontend/.env.local`):

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

The backend already enables CORS for all origins and serves uploaded detection
images under `/uploads`, so the dashboard can call the API and render images
directly. For a production build use `npm run build && npm start`. The Streamlit
app (`dashboard/`) remains available as a lightweight alternate UI.

### One-liner

```bash
./scripts/run_local.sh      # venv + install + (optional) ollama pull + seed + API + dashboard
```

### Docker

```bash
make docker-up      # builds & starts ollama + api + dashboard
# API:       http://localhost:8000   (Swagger /docs)
# Dashboard: http://localhost:8501
make docker-down
```

After the Ollama container is up, pull the model once:

```bash
docker exec -it scg-ollama ollama pull llama3.2:1b
```

### Common make targets

| Target          | Description                                  |
| --------------- | -------------------------------------------- |
| `make install`  | Create venv and install dependencies         |
| `make serve`    | Run the FastAPI API                          |
| `make dashboard`| Run the Streamlit dashboard                  |
| `make seed`     | Insert demo incidents                        |
| `make train-help`| Show the YOLOv8 training command            |
| `make eval`     | Evaluate the model (mAP / precision / recall)|
| `make test`     | Run the test suite                           |
| `make docker-up`/`make docker-down` | Manage the Docker stack  |

---

## API at a glance

Base URL `http://localhost:8000` · interactive docs at `/docs`.

| Method | Path                   | Purpose                                  |
| ------ | ---------------------- | ---------------------------------------- |
| GET    | `/health`              | Liveness + model/db/ollama status        |
| POST   | `/detect`              | Detect on one image -> stored incident   |
| POST   | `/detect/batch`        | Detect on many images                    |
| GET    | `/incidents`           | List/filter incidents                    |
| GET    | `/incidents/{id}`      | Fetch one incident                       |
| PATCH  | `/incidents/{id}`      | Update status                            |
| DELETE | `/incidents/{id}`      | Delete an incident                       |
| GET    | `/analytics/summary`   | Aggregate counts + trend                 |
| GET    | `/analytics/hotspots`  | Geospatial hotspot clusters              |

Full reference with curl examples: [`docs/api.md`](docs/api.md).

---

## Results

> Placeholders - fill in after training/evaluation. See [`docs/brief.md`](docs/brief.md)
> for the full methodology and rubric mapping.

### Detection metrics

| Metric          | YOLOv8s | YOLOv8m |
| --------------- | ------- | ------- |
| mAP@0.5         | _TBD_   | _TBD_   |
| mAP@0.5:0.95    | _TBD_   | _TBD_   |
| Precision       | _TBD_   | _TBD_   |
| Recall          | _TBD_   | _TBD_   |
| F1              | _TBD_   | _TBD_   |

### Per-class AP@0.5

| Class   | AP@0.5 |
| ------- | ------ |
| Glass   | _TBD_  |
| Metal   | _TBD_  |
| Paper   | _TBD_  |
| Plastic | _TBD_  |
| Waste   | _TBD_  |

### Latency (ms/image)

| Device              | YOLOv8s | YOLOv8m |
| ------------------- | ------- | ------- |
| CPU (Apple Silicon) | _TBD_   | _TBD_   |
| GPU (Colab T4)      | _TBD_   | _TBD_   |

---

## Screenshots

> Add images to `docs/` and reference them here.

- Dashboard map view: `docs/screenshot_map.png`
- Filters & incident table: `docs/screenshot_filters.png`
- Analytics charts: `docs/screenshot_analytics.png`
- Detection + generated incident report: `docs/screenshot_detection.png`

---

## Repository map

```
smart-city-garbage/
├── app/                  # FastAPI service
│   ├── main.py           # app + lifespan (warm-loads detector)
│   ├── config.py         # pydantic-settings (.env)
│   ├── detector.py       # YOLOv8 wrapper (Detector)
│   ├── models.py         # SQLAlchemy ORM (incidents table)
│   ├── schemas.py        # pydantic v2 schemas
│   ├── seed.py           # demo incident seeder
│   ├── routers/          # detect, incidents, analytics endpoints
│   └── llm/              # base, ollama_provider, prompts, rules, factory
├── ml/                   # dataset.yaml, prepare_data, train, evaluate, weights/
├── frontend/             # Next.js "CityGuard AI" dashboard (primary UI)
│   ├── app/              # App Router pages: /, map, incidents, analytics, detect, api-docs
│   ├── components/       # shared UI (sidebar, charts, map)
│   └── lib/              # API client (NEXT_PUBLIC_API_URL)
├── dashboard/            # Streamlit app (map / filters / analytics, alternate UI)
├── tests/                # pytest suite
├── samples/              # sample images for the demo
├── scripts/run_local.sh  # one-command local bring-up
├── docs/                 # architecture, api, brief, demo_script
├── Dockerfile.api
├── Dockerfile.dashboard
├── docker-compose.yml
├── Makefile
├── requirements.txt
├── .env.example
└── LICENSE
```

---

## Documentation

- [`docs/architecture.md`](docs/architecture.md) - pipeline diagram & data flow
- [`docs/api.md`](docs/api.md) - full REST reference with curl examples
- [`docs/brief.md`](docs/brief.md) - graded technical brief & rubric mapping
- [`docs/demo_script.md`](docs/demo_script.md) - demo video shot list

---

## License

[MIT](LICENSE) © 2026 Smart City Garbage Detection.
