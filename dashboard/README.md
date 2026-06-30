# Dashboard

Streamlit operator dashboard for the Smart City illegal garbage dumping
detection system. It is a thin client over the FastAPI backend; it holds no
business logic of its own.

## Configuration

| Variable  | Default                 | Purpose                          |
|-----------|-------------------------|----------------------------------|
| `API_URL` | `http://localhost:8000` | Base URL of the FastAPI backend. |

## Run

Start the backend first, then the dashboard:

```bash
# 1. backend (from the project root)
uvicorn app.main:app --reload

# 2. dashboard
streamlit run dashboard/app.py
# or against a remote API:
API_URL=https://api.example.com streamlit run dashboard/app.py
```

## Features

- **Sidebar filters** — department, severity, status, priority, and a date
  range. These drive `GET /incidents` and feed every tab.
- **Incidents tab** — filtered table; select a row to view the full report and
  to update status (`PATCH /incidents/{id}`) or delete it
  (`DELETE /incidents/{id}`).
- **Upload & Detect tab** — upload an image with optional lat/lon/address,
  call `POST /detect`, and render the returned incident report (severity badge,
  department, priority, SLA, description, recommended action).
- **Map tab** — incidents plotted with Folium via `streamlit-folium`, markers
  colored by severity with detail popups. Falls back to `st.map` if Folium is
  not installed.
- **Analytics tab** — KPI metric cards plus bar charts (by department,
  severity, status) and a trend line from `GET /analytics/summary`, and a
  hotspots table from `GET /analytics/hotspots`.

If the backend is unreachable the dashboard shows a clear error and stops
rather than throwing tracebacks.
