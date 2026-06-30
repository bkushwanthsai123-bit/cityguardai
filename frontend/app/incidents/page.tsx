"use client";

import { useCallback, useEffect, useState } from "react";
import { X, Trash2, Filter } from "lucide-react";
import {
  Incident,
  IncidentFilters,
  Status,
  getIncidents,
  patchIncident,
  deleteIncident,
  imageUrl,
} from "@/lib/api";
import { PageHeader } from "@/components/ui/SectionTitle";
import { Card } from "@/components/ui/Card";
import { SeverityBadge, StatusBadge } from "@/components/ui/Badge";
import { LoadingBlock, Spinner } from "@/components/ui/Spinner";
import { ErrorState, EmptyState } from "@/components/ui/EmptyState";

const SEVERITIES = ["low", "medium", "high", "critical"];
const STATUSES: Status[] = ["open", "in_progress", "resolved"];
const PRIORITIES = ["P1", "P2", "P3", "P4"];

function fmtDate(s: string) {
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function IncidentsPage() {
  const [filters, setFilters] = useState<IncidentFilters>({});
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [departments, setDepartments] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Incident | null>(null);
  const [mutating, setMutating] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const inc = await getIncidents(filters);
      setIncidents(inc);
      setDepartments((prev) => {
        const set = new Set(prev);
        inc.forEach((i) => set.add(i.department));
        return Array.from(set).sort();
      });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load incidents");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  function setFilter(key: keyof IncidentFilters, value: string) {
    setFilters((f) => ({ ...f, [key]: value || undefined }));
  }

  async function changeStatus(status: Status) {
    if (!selected) return;
    setMutating(true);
    try {
      const updated = await patchIncident(selected.id, status);
      setSelected(updated);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    } finally {
      setMutating(false);
    }
  }

  async function removeIncident() {
    if (!selected) return;
    if (!confirm(`Delete incident #${selected.id}? This cannot be undone.`))
      return;
    setMutating(true);
    try {
      await deleteIncident(selected.id);
      setSelected(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setMutating(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Incidents"
        subtitle="Manage and triage reported illegal dumping incidents"
      />

      {/* Filters */}
      <Card className="mb-5">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-sm text-[#8b909c]">
            <Filter className="h-4 w-4" />
            Filters
          </div>
          <FilterSelect
            label="Severity"
            value={filters.severity ?? ""}
            options={SEVERITIES}
            onChange={(v) => setFilter("severity", v)}
          />
          <FilterSelect
            label="Status"
            value={filters.status ?? ""}
            options={STATUSES}
            onChange={(v) => setFilter("status", v)}
          />
          <FilterSelect
            label="Priority"
            value={filters.priority ?? ""}
            options={PRIORITIES}
            onChange={(v) => setFilter("priority", v)}
          />
          <FilterSelect
            label="Department"
            value={filters.department ?? ""}
            options={departments}
            onChange={(v) => setFilter("department", v)}
          />
          {Object.values(filters).some(Boolean) && (
            <button
              type="button"
              onClick={() => setFilters({})}
              className="ml-auto rounded-lg border border-[#1e222b] px-3 py-1.5 text-xs text-[#8b909c] transition-colors hover:bg-[#15181e] hover:text-[#e7e9ee]"
            >
              Clear filters
            </button>
          )}
        </div>
      </Card>

      {loading && <LoadingBlock />}
      {!loading && error && <ErrorState message={error} />}
      {!loading && !error && incidents.length === 0 && (
        <EmptyState
          title="No incidents match"
          description="Try adjusting or clearing the filters."
        />
      )}

      {!loading && !error && incidents.length > 0 && (
        <Card padded={false}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#1e222b] text-left text-xs uppercase tracking-wide text-[#8b909c]">
                  <th className="px-5 py-3 font-medium">ID</th>
                  <th className="px-5 py-3 font-medium">Created</th>
                  <th className="px-5 py-3 font-medium">Severity</th>
                  <th className="px-5 py-3 font-medium">Priority</th>
                  <th className="px-5 py-3 font-medium">Department</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium text-right">Score</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((inc) => (
                  <tr
                    key={inc.id}
                    onClick={() => setSelected(inc)}
                    className="cursor-pointer border-b border-[#15181e] transition-colors last:border-0 hover:bg-[#15181e]"
                  >
                    <td className="px-5 py-3 font-mono text-[#8b909c]">
                      #{inc.id}
                    </td>
                    <td className="px-5 py-3 text-[#8b909c]">
                      {fmtDate(inc.created_at)}
                    </td>
                    <td className="px-5 py-3">
                      <SeverityBadge severity={inc.severity} />
                    </td>
                    <td className="px-5 py-3 text-[#e7e9ee]">{inc.priority}</td>
                    <td className="px-5 py-3 text-[#e7e9ee]">
                      {inc.department}
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge status={inc.status} />
                    </td>
                    <td className="px-5 py-3 text-right font-mono text-[#e7e9ee]">
                      {inc.severity_score.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Drawer */}
      {selected && (
        <Drawer
          incident={selected}
          mutating={mutating}
          onClose={() => setSelected(null)}
          onStatus={changeStatus}
          onDelete={removeIncident}
        />
      )}
    </div>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-lg border border-[#1e222b] bg-[#0c0e12] px-3 py-1.5 text-sm text-[#e7e9ee] outline-none focus:border-[#3b82f6]"
    >
      <option value="">{label}: All</option>
      {options.map((o) => (
        <option key={o} value={o}>
          {o.replace("_", " ")}
        </option>
      ))}
    </select>
  );
}

function Drawer({
  incident,
  mutating,
  onClose,
  onStatus,
  onDelete,
}: {
  incident: Incident;
  mutating: boolean;
  onClose: () => void;
  onStatus: (s: Status) => void;
  onDelete: () => void;
}) {
  const img = imageUrl(incident.image_path);
  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative z-50 h-full w-full max-w-md overflow-y-auto border-l border-[#1e222b] bg-[#0c0e12] shadow-2xl">
        <div className="sticky top-0 flex items-center justify-between border-b border-[#1e222b] bg-[#0c0e12] px-5 py-4">
          <div>
            <p className="font-mono text-xs text-[#8b909c]">#{incident.id}</p>
            <h3 className="text-base font-semibold text-[#e7e9ee]">
              {incident.title}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-[#8b909c] transition-colors hover:bg-[#15181e] hover:text-[#e7e9ee]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-5 p-5">
          {img && (
            <div className="overflow-hidden rounded-lg border border-[#1e222b]">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={img}
                alt={incident.title}
                className="max-h-60 w-full object-cover"
              />
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={incident.severity} />
            <StatusBadge status={incident.status} />
            <span className="rounded-full border border-[#1e222b] bg-[#111317] px-2.5 py-0.5 text-xs font-medium text-[#e7e9ee]">
              {incident.priority}
            </span>
            <span className="text-xs text-[#8b909c]">
              score {incident.severity_score.toFixed(2)}
            </span>
          </div>

          <DrawerRow label="Department" value={incident.department} />
          <DrawerRow label="SLA" value={`${incident.sla_hours} hours`} />
          {incident.address && (
            <DrawerRow label="Address" value={incident.address} />
          )}
          {incident.lat != null && incident.lon != null && (
            <DrawerRow
              label="Coordinates"
              value={`${incident.lat.toFixed(4)}, ${incident.lon.toFixed(4)}`}
            />
          )}

          <Block label="Description">{incident.description}</Block>
          <Block label="Recommended action">
            {incident.recommended_action}
          </Block>

          <div>
            <p className="mb-2 text-xs uppercase tracking-wide text-[#8b909c]">
              Detections ({incident.num_detections})
            </p>
            {incident.detections.length === 0 ? (
              <p className="text-sm text-[#8b909c]">No detections.</p>
            ) : (
              <div className="space-y-2">
                {incident.detections.map((d, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between rounded-lg border border-[#1e222b] bg-[#111317] px-3 py-2 text-sm"
                  >
                    <span className="text-[#e7e9ee]">{d.class_name}</span>
                    <span className="flex gap-3 text-xs text-[#8b909c]">
                      <span>{(d.confidence * 100).toFixed(1)}%</span>
                      <span>area {(d.area_fraction * 100).toFixed(1)}%</span>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="space-y-3 border-t border-[#1e222b] pt-4">
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-[#8b909c]">
                Update status
              </span>
              <select
                value={incident.status}
                disabled={mutating}
                onChange={(e) => onStatus(e.target.value as Status)}
                className="w-full rounded-lg border border-[#1e222b] bg-[#111317] px-3 py-2 text-sm text-[#e7e9ee] outline-none focus:border-[#3b82f6] disabled:opacity-50"
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s.replace("_", " ")}
                  </option>
                ))}
              </select>
            </label>

            <button
              type="button"
              onClick={onDelete}
              disabled={mutating}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-[#ef444433] bg-[#ef44440d] px-4 py-2 text-sm font-medium text-[#ef4444] transition-colors hover:bg-[#ef44441a] disabled:opacity-50"
            >
              {mutating ? <Spinner size={16} /> : <Trash2 className="h-4 w-4" />}
              Delete incident
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function DrawerRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 text-sm">
      <span className="text-[#8b909c]">{label}</span>
      <span className="text-right font-medium text-[#e7e9ee]">{value}</span>
    </div>
  );
}

function Block({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-[#8b909c]">{label}</p>
      <p className="mt-1 text-sm leading-relaxed text-[#e7e9ee]">{children}</p>
    </div>
  );
}
