export const API =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Severity = "low" | "medium" | "high" | "critical";
export type Priority = "P1" | "P2" | "P3" | "P4";
export type Status = "open" | "in_progress" | "resolved";

export interface Detection {
  class_name: string;
  confidence: number;
  bbox: [number, number, number, number];
  area_fraction: number;
}

export interface Incident {
  id: number;
  created_at: string;
  image_path: string | null;
  annotated_path: string | null;
  detections: Detection[];
  num_detections: number;
  classes: string[];
  lat: number | null;
  lon: number | null;
  address: string | null;
  title: string;
  description: string;
  severity: Severity;
  severity_score: number;
  priority: Priority;
  department: string;
  recommended_action: string;
  sla_hours: number;
  status: Status;
}

export interface SummaryBucket {
  name: string;
  count: number;
}

export interface TrendPoint {
  date: string;
  count: number;
}

export interface AnalyticsSummary {
  total: number;
  by_status: Record<string, number>;
  by_severity: Record<string, number>;
  by_department: Record<string, number>;
  by_priority?: Record<string, number>;
  trend: TrendPoint[];
}

export interface Hotspot {
  lat: number;
  lon: number;
  count: number;
  top_severity: Severity;
  address?: string | null;
}

export interface IncidentFilters {
  severity?: string;
  status?: string;
  department?: string;
  priority?: string;
}

async function getJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    cache: "no-store",
    ...init,
  });
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export function getHealth(): Promise<{ status: string } & Record<string, unknown>> {
  return getJSON("/health");
}

export function getIncidents(
  filters: IncidentFilters = {}
): Promise<Incident[]> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v) params.set(k, v);
  });
  const qs = params.toString();
  return getJSON<Incident[]>(`/incidents${qs ? `?${qs}` : ""}`);
}

export function getIncident(id: number): Promise<Incident> {
  return getJSON<Incident>(`/incidents/${id}`);
}

export function patchIncident(id: number, status: Status): Promise<Incident> {
  return getJSON<Incident>(`/incidents/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

export async function deleteIncident(id: number): Promise<void> {
  const res = await fetch(`${API}/incidents/${id}`, { method: "DELETE" });
  if (!res.ok) {
    throw new Error(`Delete failed: ${res.status} ${res.statusText}`);
  }
}

export interface DetectMeta {
  lat?: number | null;
  lon?: number | null;
  address?: string | null;
}

export async function detect(
  file: File,
  meta: DetectMeta = {}
): Promise<Incident> {
  const form = new FormData();
  form.append("file", file);
  if (meta.lat !== undefined && meta.lat !== null)
    form.append("lat", String(meta.lat));
  if (meta.lon !== undefined && meta.lon !== null)
    form.append("lon", String(meta.lon));
  if (meta.address) form.append("address", meta.address);

  const res = await fetch(`${API}/detect`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    throw new Error(`Detection failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as Incident;
}

export async function detectVideo(
  file: File,
  meta: DetectMeta = {},
  maxFrames = 24
): Promise<Incident> {
  const form = new FormData();
  form.append("file", file);
  form.append("max_frames", String(maxFrames));
  if (meta.lat !== undefined && meta.lat !== null)
    form.append("lat", String(meta.lat));
  if (meta.lon !== undefined && meta.lon !== null)
    form.append("lon", String(meta.lon));
  if (meta.address) form.append("address", meta.address);

  const res = await fetch(`${API}/detect/video`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    throw new Error(`Video detection failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as Incident;
}

export function getSummary(): Promise<AnalyticsSummary> {
  return getJSON<AnalyticsSummary>("/analytics/summary");
}

export function getHotspots(): Promise<Hotspot[]> {
  return getJSON<Hotspot[]>("/analytics/hotspots");
}

export function imageUrl(image_path: string | null): string | null {
  if (!image_path) return null;
  const clean = image_path.replace(/^\/+/, "");
  return `${API}/${clean}`;
}

export const SEVERITY_COLORS: Record<Severity, string> = {
  low: "#22c55e",
  medium: "#eab308",
  high: "#f97316",
  critical: "#ef4444",
};

export const STATUS_LABELS: Record<Status, string> = {
  open: "Open",
  in_progress: "In Progress",
  resolved: "Resolved",
};
