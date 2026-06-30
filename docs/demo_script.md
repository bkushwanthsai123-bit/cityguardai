# Demo Video Script (5-10 minutes)

A timestamped shot list for recording the project walkthrough. Target length
~7 minutes. Keep narration tight; show the working system more than slides.

## Pre-recording checklist

- [ ] `source .venv/bin/activate`
- [ ] `ollama pull llama3.2:1b` done and Ollama running
- [ ] `python -m app.seed` run so the dashboard is populated
- [ ] API up: `uvicorn app.main:app` (verify `http://localhost:8000/health`)
- [ ] Dashboard up: `streamlit run dashboard/app.py`
- [ ] Sample images ready in `samples/` (at least one clear dumping image)
- [ ] Browser tabs: Swagger `/docs`, dashboard `:8501`
- [ ] Screen recorder + mic levels checked

---

## Shot list

### 0:00-0:45 - Problem intro

- **Visual:** title slide, then a couple of real street-dumping photos.
- **Narration:** Illegal garbage dumping is costly and slow to act on because
  reports are unstructured. This project automatically detects dumping in
  imagery, generates a routed, prioritized incident, and maps it for city teams.
- **Say the stack in one line:** YOLOv8 + local LLM (Ollama) + FastAPI + SQLite
  + Streamlit.

### 0:45-1:45 - Architecture overview

- **Visual:** `docs/architecture.md` Mermaid diagram (or exported
  `architecture.png`).
- **Narration:** Walk the flow: image -> FastAPI `/detect` -> YOLOv8 detector ->
  LLM layer (Ollama drafts the prose, deterministic rules own the numbers) ->
  SQLite -> REST -> dashboard. Emphasize the guardrail design and graceful
  fallbacks (missing weights -> yolov8n, Ollama down -> rules).

### 1:45-3:00 - Dataset & training results

- **Visual:** `ml/dataset.yaml` (4 classes), a few labeled sample images, then
  the metrics tables in `docs/brief.md` / training curves.
- **Narration:** Explain the 4 classes and why YOLOv8s (speed/accuracy balance,
  edge-deployable) with YOLOv8m as the higher-accuracy option. Show mAP@0.5,
  mAP@0.5:0.95, precision/recall/F1, and per-class AP. Mention CPU vs Colab GPU
  latency.

### 3:00-4:30 - Live detection + LLM incident report

- **Visual:** Swagger `/docs` -> `POST /detect`, upload `samples/dump1.jpg` with
  `lat`/`lon`/`address`. (Or a small upload UI if available.)
- **Narration:** Point out the JSON response: detected classes with confidence
  and bounding boxes, then the generated `IncidentReport` - title, description,
  recommended_action from the LLM, and severity_score/band, priority,
  department, sla_hours from the rules.
- **Highlight the guardrail:** note that severity and routing are deterministic
  and validated, so the LLM cannot produce invalid operational data.
- **Optional:** stop Ollama and re-run to show the rules-only fallback still
  returns a valid incident.

### 4:30-6:00 - Dashboard: map, filters, analytics

- **Visual:** Streamlit dashboard at `:8501`.
- **Map:** show hotspots over the city (seeded around Bengaluru); click a marker
  to see incident details.
- **Filters:** filter by department, severity, status, priority, and date; show
  the table/map updating.
- **Analytics:** show the summary charts - counts by severity/department/status/
  priority and the daily trend line. Tie it back to operations: where is dumping
  worst, who owns it, are SLAs being met.

### 6:00-6:40 - Architecture recap & engineering highlights

- **Visual:** repo map (README) + a glance at `app/llm/` and `app/detector.py`.
- **Narration:** Recap the engineering: vendor-agnostic `AIProvider`, typed
  pydantic schemas, REST-only dashboard boundary, SQLite->Postgres swap via one
  `DB_URL`, Dockerized 3-service stack, and graceful degradation throughout.

### 6:40-7:15 - Closing

- **Visual:** title slide / GitHub repo.
- **Narration:** Summarize impact: raw images become routed, prioritized,
  SLA-bound incidents on a live map - usable by city dispatch today. Mention
  scalability (horizontal API, edge export, batch ingestion) and that it runs
  fully locally and offline. Thank the viewer; point to the README quickstart.

---

## Tips

- Pre-run one `/detect` before recording so model/LLM are warm (avoids first-call
  latency on camera).
- Keep the camera on the running system; narrate over real responses, not slides.
- If recording without GPU, mention CPU latency numbers so expectations are set.
