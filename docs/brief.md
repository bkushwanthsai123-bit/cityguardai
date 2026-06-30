# Technical Brief - Smart City Illegal Garbage Dumping Detection

This brief documents the design decisions, methodology, and results for the
system, and maps each section to the grading rubric.

## Rubric mapping

| Weight | Criterion       | Where addressed                                            |
| ------ | --------------- | ---------------------------------------------------------- |
| 30%    | ML accuracy     | [Model choice](#1-model-choice), [Dataset](#2-dataset), [Evaluation](#3-evaluation-metrics) |
| 20%    | LLM             | [LLM workflow design](#5-llm-workflow-design)              |
| 20%    | System design   | [Deployment](#6-deployment-approach), [Architecture](architecture.md) |
| 15%    | Code quality    | [Code quality](#7-code-quality)                            |
| 10%    | Scalability     | [Scalability](#8-scalability)                              |
| 5%     | Innovation      | [Innovation](#9-innovation)                                |

---

## 1. Model choice

We use **Ultralytics YOLOv8** for object detection, evaluating two sizes:

- **YOLOv8s (small)** - the default. ~11M params; strong accuracy/latency
  balance that runs in real time on a single CPU/edge device, which matters for
  city deployments where GPU is not guaranteed at every ingest point.
- **YOLOv8m (medium)** - ~26M params; higher mAP for a centralized/GPU-backed
  deployment when accuracy is prioritized over per-image latency.

**Why YOLOv8 over alternatives:**

- **Single-stage, anchor-free** detector: fast and simple to train/serve versus
  two-stage detectors (Faster R-CNN) that are heavier to deploy.
- **Mature tooling**: one-line training/eval/export, ONNX/TensorRT export for
  edge, active maintenance.
- **Right granularity**: garbage objects are mid-to-large, well-suited to
  YOLO's grid; we do not need instance segmentation for incident routing, so
  detection (bounding boxes) keeps the model light.
- **s -> m -> l ladder** lets us trade accuracy for latency without changing any
  code, only the weights file.

**Classes (5, fixed index order):** `Glass`, `Metal`, `Paper`, `Plastic`,
`Waste`. The order is shared across `ml/dataset.yaml` and `app/detector.py`. The
active model is a pretrained YOLOv8m-seg trash detector (`ml/weights/best.pt`,
~0.43 mAP@0.5 on TACO); retraining via the Colab notebook yields higher accuracy.

---

## 2. Dataset

- **Sources:** public waste/garbage detection datasets (e.g. TACO - Trash
  Annotations in Context, open street-litter sets) plus curated/labeled
  street-level images, normalized to the 5 project classes.
- **Annotation format:** YOLO TXT (one `.txt` per image: `class cx cy w h`,
  normalized), described by `ml/dataset.yaml`.
- **Splits:** train / val / test (recommended ~70/20/10).
- **Augmentation:** Ultralytics defaults (mosaic, HSV jitter, flips, scale) to
  improve robustness to lighting, angle, and clutter typical of street imagery.
- **Class balance:** monitor per-class instance counts; oversample or weight
  rarer classes (e.g. `Glass`) if AP lags.

> Fill in final counts after `make prepare`:
>
> | Split | Images | Instances |
> | ----- | ------ | --------- |
> | train | _TBD_  | _TBD_     |
> | val   | _TBD_  | _TBD_     |
> | test  | _TBD_  | _TBD_     |

---

## 3. Evaluation metrics

Run `make eval` (`ml/evaluate.py`) on the held-out set. Report mAP@0.5,
mAP@0.5:0.95, precision, recall, F1, and per-class AP.

### Overall (template)

| Metric         | YOLOv8s | YOLOv8m |
| -------------- | ------- | ------- |
| mAP@0.5        | _TBD_   | _TBD_   |
| mAP@0.5:0.95   | _TBD_   | _TBD_   |
| Precision      | _TBD_   | _TBD_   |
| Recall         | _TBD_   | _TBD_   |
| F1             | _TBD_   | _TBD_   |

### Per-class AP@0.5 (template)

| Class   | AP@0.5 (s) | AP@0.5 (m) |
| ------- | ---------- | ---------- |
| Glass   | _TBD_      | _TBD_      |
| Metal   | _TBD_      | _TBD_      |
| Paper   | _TBD_      | _TBD_      |
| Plastic | _TBD_      | _TBD_      |
| Waste   | _TBD_      | _TBD_      |

### Confusion / error analysis (notes)

- Expected confusions: `Plastic` vs `Waste` (overlap in mixed dumping);
  `Paper` vs background (small objects). Document and discuss after evaluation.

---

## 4. Latency

Measured as model inference time per image (`inference_ms` in `DetectionResult`),
plus end-to-end including the LLM step.

### Inference latency (template, ms/image)

| Device                  | YOLOv8s | YOLOv8m |
| ----------------------- | ------- | ------- |
| CPU (Apple Silicon M-series) | _TBD_ | _TBD_ |
| GPU (Google Colab T4)   | _TBD_   | _TBD_   |

### End-to-end (template)

| Stage                         | Time (ms) |
| ----------------------------- | --------- |
| YOLOv8 inference              | _TBD_     |
| LLM report (Ollama llama3.2:1b)| _TBD_    |
| Rules + DB persist            | _TBD_     |
| **Total /detect**             | _TBD_     |

> Note: the rules-only fallback path removes the LLM latency entirely, useful for
> high-throughput batch ingestion.

---

## 5. LLM workflow design

The LLM turns raw detections into an **actionable incident report** while staying
strictly bounded so it can never produce invalid operational data.

**Provider abstraction.** `app/llm/base.py` defines an `AIProvider` interface
(`generate_report(result, context) -> IncidentReport`). `factory.get_provider()`
selects the implementation from `LLM_PROVIDER` (default `ollama`), keeping the
system vendor-agnostic.

**Ollama provider.** `ollama_provider.py` calls Ollama (`/api/chat`) with
`format="json"`, model `LLM_MODEL` (default `llama3.2:1b`), against `OLLAMA_HOST`.
The default is a lightweight, CPU-friendly 1B model (~4s/report on an Apple M1
with no GPU); swap `LLM_MODEL` for a larger model (e.g. `llama3.1:8b`) if a GPU
is available. The prompt (`prompts.py`) is a system prompt + few-shot examples
instructing strict JSON output matching the `IncidentReport` schema.

**Bounded reasoning - rules own the numbers.** This is the key design choice:

- The LLM authors only **prose**: `title`, `description`, `recommended_action`.
- **Deterministic rules (`rules.py`) always run** to compute and clamp
  `severity_score`, `severity` band, `priority`, `department`, and `sla_hours`,
  so the LLM cannot emit out-of-range or inconsistent values.
- Scoring formula:
  `score = min(100, round(100 * Σ(class_weight * bbox_area_fraction) + 5*count_bonus))`
  with weights `Waste=1.0, Glass=0.8, Metal=0.6, Plastic=0.6, Paper=0.4` and
  `count_bonus = min(detection_count, 5)`.
- Bands: 0-25 low, 26-50 medium, 51-75 high, 76-100 critical. Priority:
  critical->P1, high->P2, medium->P3, low->P4. SLA: P1=4, P2=12, P3=24, P4=72 h.
- Department routing: `Waste`/`Glass`/`Metal` -> Solid Waste Management;
  `Plastic` -> Sanitation Department; `Paper` -> Street Cleaning / Public Health;
  mixed -> highest-weight class present.

**Reliability.** On JSON parse failure the provider retries once; if Ollama is
unreachable it falls back entirely to `rules.build_report()`, which produces a
complete valid report with rule-generated text. Result: the system is robust,
reproducible, and never blocked by LLM availability.

---

## 6. Deployment approach

- **Local dev:** `python -m venv` + `pip install -r requirements.txt`, then
  `uvicorn app.main:app` and `streamlit run dashboard/app.py`. One-command
  bring-up via `scripts/run_local.sh`. Tested on macOS Apple Silicon.
- **Primary frontend:** a production-style Next.js + Tailwind dashboard in
  `frontend/` (`npm install && npm run dev`, served on port 3000) consuming the
  same REST API; the backend points are configured via `NEXT_PUBLIC_API_URL`.
- **Runtime requirements:** Python 3.10+ is required (we run 3.12) because the
  codebase uses `from __future__ import annotations` with PEP 604 `X | Y` unions
  that Python 3.9 cannot evaluate at runtime. `requirements.txt` pins
  `ultralytics>=8.4.0`: older 8.2.x releases break under PyTorch 2.6+, which
  defaults to `weights_only=True` checkpoint loading. The detector falls back to
  `yolov8n.pt` until a trained `ml/weights/best.pt` exists, so detections are
  empty until training is complete. The browser frontend relies on the API's
  CORS (all origins) and the `/uploads` static mount for detection images.
- **Containerized:** `docker compose up` starts three services - `ollama`,
  `api` (FastAPI + YOLOv8), and `dashboard` (Streamlit) - with healthchecks and
  a shared volume holding the SQLite DB and uploads. Ollama runs as its own
  container; the model is pulled once.
- **Config-driven:** all environment-specific values (`DB_URL`, `MODEL_PATH`,
  `OLLAMA_HOST`, `LLM_MODEL`, `CONF_THRESHOLD`, `UPLOAD_DIR`) come from `.env`
  via pydantic-settings, so the same image runs in any environment.
- **Graceful degradation:** missing weights fall back to `yolov8n.pt`;
  unreachable Ollama falls back to rules - the service always boots and serves.

---

## 7. Code quality

- **Typed and documented:** pydantic v2 schemas with exact field contracts;
  docstrings on public functions; relative imports within `app`.
- **Separation of concerns:** detection, LLM reasoning, persistence, and
  presentation are independent, independently-importable modules; the dashboard
  talks only to the REST API.
- **Single source of truth:** a shared contract fixes schemas, endpoints, class
  order, and scoring so all modules integrate cleanly.
- **Testing:** `pytest` suite (`make test`) covers rules math, schema
  validation, and API behavior.
- **Fail-loud:** warnings on fallbacks (missing weights, Ollama down) rather
  than silent misbehavior.
- **Reproducible env:** pinned `requirements.txt`, `.env.example`, Makefile, and
  Docker for deterministic setup.

---

## 8. Scalability

- **Stateless API:** the FastAPI service holds no client state; scale
  horizontally behind a load balancer. The detector is warm-loaded per worker.
- **Database swap:** SQLite for dev; change one `DB_URL` to move to Postgres for
  concurrent, production-grade writes - no code changes.
- **Batch ingestion:** `/detect/batch` and the rules-only fast path support
  high-throughput pipelines (e.g. CCTV frame streams).
- **Decoupled LLM:** Ollama is a separate service; it can be scaled, replaced,
  or pointed at a remote endpoint independently of detection.
- **Edge-ready models:** YOLOv8 exports to ONNX/TensorRT for on-device inference,
  pushing detection to the edge and sending only structured incidents upstream.
- **Geospatial queries:** bounding-box filters and hotspot aggregation are
  designed to migrate to PostGIS spatial indexes as data grows.

---

## 9. Innovation

- **LLM + deterministic guardrails hybrid:** the LLM provides natural-language
  reasoning while rules guarantee valid, reproducible operational numbers - the
  best of both without hallucinated severities or SLAs.
- **Vendor-agnostic, fully local LLM:** runs entirely offline on a local Ollama
  model - privacy-preserving and zero per-call cost, important for public-sector
  deployments.
- **Operations-first output:** every detection becomes a routed, prioritized,
  SLA-bound incident on a live map, not just a bounding box - directly usable by
  city dispatch teams.
- **Production-style operations console:** a polished dark Next.js + Tailwind
  "CityGuard AI" dashboard - sidebar navigation, a detection-pipeline
  visualization, a model card, a dark interactive map, and analytics charts -
  consumes the same REST API as the lightweight Streamlit app, demonstrating
  that the backend cleanly supports multiple, independently evolvable clients.
- **Graceful degradation everywhere:** the system stays useful even with no GPU,
  no trained weights, and no LLM.
