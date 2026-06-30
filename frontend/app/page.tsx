"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ClipboardList,
  FolderOpen,
  Loader2,
  CheckCircle2,
} from "lucide-react";
import {
  AnalyticsSummary,
  Incident,
  getSummary,
  getIncidents,
} from "@/lib/api";
import { PageHeader, SectionTitle } from "@/components/ui/SectionTitle";
import { KpiCard } from "@/components/ui/KpiCard";
import { Card } from "@/components/ui/Card";
import { SeverityBadge, StatusBadge } from "@/components/ui/Badge";
import { LoadingBlock } from "@/components/ui/Spinner";
import { ErrorState, EmptyState } from "@/components/ui/EmptyState";
import { SimpleBar, TrendArea, recordToData } from "@/components/Charts";

const SEV_ORDER = ["low", "medium", "high", "critical"];
const STATUS_ORDER = ["open", "in_progress", "resolved"];

function fmtDate(s: string) {
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function DashboardPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [recent, setRecent] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        setLoading(true);
        const [s, inc] = await Promise.all([getSummary(), getIncidents()]);
        if (!active) return;
        setSummary(s);
        setRecent(inc.slice(0, 6));
        setError(null);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const byStatus = summary?.by_status ?? {};

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle="City-wide illegal dumping overview"
      />

      {loading && <LoadingBlock />}
      {!loading && error && <ErrorState message={error} />}

      {!loading && !error && summary && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              label="Total Incidents"
              value={summary.total}
              icon={<ClipboardList className="h-5 w-5" />}
              accent="#3b82f6"
            />
            <KpiCard
              label="Open"
              value={byStatus.open ?? 0}
              icon={<FolderOpen className="h-5 w-5" />}
              accent="#60a5fa"
            />
            <KpiCard
              label="In Progress"
              value={byStatus.in_progress ?? 0}
              icon={<Loader2 className="h-5 w-5" />}
              accent="#eab308"
            />
            <KpiCard
              label="Resolved"
              value={byStatus.resolved ?? 0}
              icon={<CheckCircle2 className="h-5 w-5" />}
              accent="#22c55e"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Card>
              <SectionTitle title="By Department" />
              <SimpleBar
                data={recordToData(summary.by_department)}
                color="#6366f1"
              />
            </Card>
            <Card>
              <SectionTitle title="By Severity" />
              <SimpleBar
                data={recordToData(summary.by_severity, SEV_ORDER)}
                severityColored
              />
            </Card>
            <Card>
              <SectionTitle title="By Status" />
              <SimpleBar
                data={recordToData(summary.by_status, STATUS_ORDER)}
                color="#3b82f6"
              />
            </Card>
          </div>

          <Card>
            <SectionTitle
              title="Incidents Trend"
              subtitle="Daily reported incidents"
            />
            {summary.trend.length ? (
              <TrendArea data={summary.trend} />
            ) : (
              <EmptyState title="No trend data yet" />
            )}
          </Card>

          <Card padded={false}>
            <div className="p-5 pb-3">
              <SectionTitle
                title="Recent Incidents"
                subtitle="Latest 6 reports"
              />
            </div>
            {recent.length === 0 ? (
              <div className="p-5 pt-0">
                <EmptyState
                  title="No incidents yet"
                  description="Run a detection to create the first incident."
                />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-y border-[#1e222b] text-left text-xs uppercase tracking-wide text-[#8b909c]">
                      <th className="px-5 py-3 font-medium">ID</th>
                      <th className="px-5 py-3 font-medium">Created</th>
                      <th className="px-5 py-3 font-medium">Severity</th>
                      <th className="px-5 py-3 font-medium">Department</th>
                      <th className="px-5 py-3 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recent.map((inc) => (
                      <tr
                        key={inc.id}
                        onClick={() => router.push("/incidents")}
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
                        <td className="px-5 py-3 text-[#e7e9ee]">
                          {inc.department}
                        </td>
                        <td className="px-5 py-3">
                          <StatusBadge status={inc.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
