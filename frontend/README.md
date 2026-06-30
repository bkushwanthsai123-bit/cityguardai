# CityGuard AI - Frontend

The primary web dashboard for the Smart City illegal garbage dumping detection
system. It is a polished dark operations console that consumes the FastAPI
backend over REST and visualizes detections, incidents, hotspots, and analytics.

Built with Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4,
lucide-react, recharts, and react-leaflet.

## Prerequisites

- Node.js 18+ and npm.
- The backend API running and reachable (default `http://localhost:8000`). From
  the repository root: `uvicorn app.main:app --reload`. The API enables CORS for
  all origins and serves uploaded detection images under `/uploads`, which this
  app loads directly.

## Install and run

```bash
npm install
npm run dev      # development server at http://localhost:3000
```

```bash
npm run build    # production build
npm start        # serve the production build
```

```bash
npm run lint     # lint
```

## Configuration

The backend base URL is read from `NEXT_PUBLIC_API_URL` (default
`http://localhost:8000`). To point at a different backend, set it in
`frontend/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Pages

- `/` - Dashboard: overview of key metrics, recent incidents, and detection pipeline status.
- `/map` - Map View: dark interactive map of incident hotspots from `/analytics/hotspots`.
- `/incidents` - Incidents: filterable table of incidents from `/incidents`, with detail, status update, and delete.
- `/analytics` - Analytics: aggregate counts and trends from `/analytics/summary`.
- `/detect` - Detect: upload an image to `POST /detect` and view the detection result and generated incident.
- `/api-docs` - API Docs: reference for the backend endpoints (links to the FastAPI Swagger UI at `/docs`).
