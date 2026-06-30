# REST API Reference

Base URL: `http://localhost:8000`
Interactive Swagger UI: `http://localhost:8000/docs` (OpenAPI schema at
`/openapi.json`).

All responses are JSON. Incident-returning endpoints emit the `IncidentOut`
shape described below.

## Schemas

### Detection

```json
{
  "class_name": "Waste",
  "confidence": 0.91,
  "bbox": [120.0, 88.0, 540.0, 470.0],
  "area_fraction": 0.34
}
```

### IncidentOut

Serialized row from the `incidents` table.

```json
{
  "id": 1,
  "created_at": "2026-07-01T08:15:00",
  "image_path": "uploads/abc123.jpg",
  "detections": [
    {"class_name": "Waste", "confidence": 0.91,
     "bbox": [120.0, 88.0, 540.0, 470.0], "area_fraction": 0.34}
  ],
  "num_detections": 1,
  "classes": ["Waste"],
  "lat": 12.9716,
  "lon": 77.5946,
  "address": "MG Road, Bengaluru",
  "title": "Large garbage pile blocking footpath",
  "description": "A sizeable accumulation of mixed waste was detected on the pedestrian path.",
  "severity": "high",
  "severity_score": 63,
  "priority": "P2",
  "department": "Solid Waste Management",
  "recommended_action": "Dispatch a collection crew and clear the pile within the SLA window.",
  "sla_hours": 12,
  "status": "open"
}
```

### IncidentUpdate (PATCH body)

```json
{ "status": "in_progress" }
```

`status` is one of `open`, `in_progress`, `resolved`.

---

## Endpoints

### GET /health

Liveness and dependency status.

```bash
curl http://localhost:8000/health
```

Response:

```json
{ "status": "ok", "model_loaded": true, "db_ok": true, "ollama_ok": true }
```

---

### POST /detect

Run detection on a single image, generate an incident report, and store it.
Multipart form: `file` (required, image), optional `lat`, `lon`, `address`.

```bash
curl -X POST http://localhost:8000/detect \
  -F "file=@samples/dump1.jpg" \
  -F "lat=12.9716" \
  -F "lon=77.5946" \
  -F "address=MG Road, Bengaluru"
```

Response: `IncidentOut` (see schema above).

---

### POST /detect/batch

Run detection on multiple images in one call. Multipart form: `files`
(repeated).

```bash
curl -X POST http://localhost:8000/detect/batch \
  -F "files=@samples/dump1.jpg" \
  -F "files=@samples/dump2.jpg"
```

Response: `List[IncidentOut]`.

---

### GET /incidents

List incidents with optional filters.

Query parameters: `department`, `severity`, `status`, `priority`, `date_from`,
`date_to`, `min_lat`, `max_lat`, `min_lon`, `max_lon`, `limit`, `offset`.

```bash
curl "http://localhost:8000/incidents?severity=high&status=open&limit=20&offset=0"
```

Geospatial bounding-box example:

```bash
curl "http://localhost:8000/incidents?min_lat=12.90&max_lat=13.05&min_lon=77.50&max_lon=77.70"
```

Response: `List[IncidentOut]`.

---

### GET /incidents/{id}

Fetch one incident. Returns `404` if not found.

```bash
curl http://localhost:8000/incidents/1
```

Response: `IncidentOut`.

---

### PATCH /incidents/{id}

Update an incident's status.

```bash
curl -X PATCH http://localhost:8000/incidents/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "in_progress"}'
```

Response: updated `IncidentOut`.

---

### DELETE /incidents/{id}

Delete an incident.

```bash
curl -X DELETE http://localhost:8000/incidents/1
```

Response:

```json
{ "deleted": true }
```

---

### GET /analytics/summary

Aggregate counts and a daily trend series.

```bash
curl http://localhost:8000/analytics/summary
```

Response:

```json
{
  "total": 42,
  "by_severity": { "low": 8, "medium": 14, "high": 15, "critical": 5 },
  "by_department": {
    "Solid Waste Management": 20,
    "Sanitation Department": 12,
    "Street Cleaning / Public Health": 10
  },
  "by_status": { "open": 25, "in_progress": 10, "resolved": 7 },
  "by_priority": { "P1": 5, "P2": 15, "P3": 14, "P4": 8 },
  "trend": [
    { "date": "2026-06-29", "count": 12 },
    { "date": "2026-06-30", "count": 18 },
    { "date": "2026-07-01", "count": 12 }
  ]
}
```

---

### GET /analytics/hotspots

Geospatial clusters of incidents for the map heat/marker layer.

```bash
curl http://localhost:8000/analytics/hotspots
```

Response:

```json
[
  { "lat": 12.9716, "lon": 77.5946, "count": 7, "top_severity": "high" },
  { "lat": 12.9352, "lon": 77.6245, "count": 3, "top_severity": "critical" }
]
```

---

## Notes

- Severity, priority, department, and SLA are deterministically computed
  server-side; they are read-only in responses (see `docs/architecture.md` and
  `docs/brief.md` for the scoring formula).
- All timestamps are UTC ISO-8601.
- Errors follow FastAPI defaults: `{"detail": "..."}` with appropriate HTTP
  status codes (e.g. `404` for a missing incident, `422` for validation errors).
