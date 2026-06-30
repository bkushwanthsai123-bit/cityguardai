"use client";

import { useEffect, useState } from "react";
import { Layers, AlertTriangle, ShieldAlert, MapPin } from "lucide-react";
import {
  AnalyticsSummary,
  Hotspot,
  getSummary,
  getHotspots,
} from "@/lib/api";
import { PageHeader, SectionTitle } from "@/components/ui/SectionTitle";
import { Card } from "@/components/ui/Card";
import { KpiCard } from "@/components/ui/KpiCard";
import { SeverityBadge } from "@/components/ui/Badge";
import { LoadingBlock } from "@/components/ui/Spinner";
import { ErrorState, EmptyState } from "@/components/ui/EmptyState";
import {
  SimpleBar,
  SeverityPie,
  TrendArea,
  recordToData,
} from "@/components/Charts";

const SEV_ORDER = ["low", "medium", "high", "critical"];
const STATUS_ORDER = ["open", "in_progress", "resolved"];

export default function AnalyticsPage() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        setLoading(true);
        const [s, h] = await Promise.all([getSummary(), getHotspots()]);
        if (!active) return;
        setSummary(s);
        setHotspots(h);
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

  const sev = summary?.by_severity ?? {};
  const critical = (sev.critical ?? 0) + (sev.high ?? 0);

  return (
    <div>
      <PageHeader
        title="Analytics"
        subtitle="Trends, distributions, and geographic hotspots"
      />

      {loading && <LoadingBlock />}
      {!loading && error && <ErrorState message={error} />}

      {!loading && !error && summary && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              label="Total Incidents"
              value={summary.total}
              icon={<Layers className="h-5 w-5" />}
              accent="#3b82f6"
            />
            <KpiCard
              label="High + Critical"
              value={critical}
              icon={<ShieldAlert className="h-5 w-5" />}
              accent="#ef4444"
            />
            <KpiCard
              label="Departments"
              value={Object.keys(summary.by_department).length}
              icon={<AlertTriangle className="h-5 w-5" />}
              accent="#eab308"
            />
            <KpiCard
              label="Hotspots"
              value={hotspots.length}
              icon={<MapPin className="h-5 w-5" />}
              accent="#6366f1"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <SectionTitle title="Incidents by Department" />
              <SimpleBar
                data={recordToData(summary.by_department)}
                color="#6366f1"
                height={300}
              />
            </Card>
            <Card>
              <SectionTitle title="Severity Distribution" />
              <SeverityPie
                data={recordToData(summary.by_severity, SEV_ORDER)}
                height={300}
              />
            </Card>
            <Card>
              <SectionTitle title="Incidents by Status" />
              <SimpleBar
                data={recordToData(summary.by_status, STATUS_ORDER)}
                color="#3b82f6"
                height={300}
              />
            </Card>
            <Card>
              <SectionTitle title="Incidents Trend" />
              {summary.trend.length ? (
                <TrendArea data={summary.trend} height={300} />
              ) : (
                <EmptyState title="No trend data yet" />
              )}
            </Card>
          </div>

          <Card padded={false}>
            <div className="p-5 pb-3">
              <SectionTitle
                title="Geographic Hotspots"
                subtitle="Clusters of incidents ranked by volume"
              />
            </div>
            {hotspots.length === 0 ? (
              <div className="p-5 pt-0">
                <EmptyState title="No geolocated incidents yet" />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-y border-[#1e222b] text-left text-xs uppercase tracking-wide text-[#8b909c]">
                      <th className="px-5 py-3 font-medium">Latitude</th>
                      <th className="px-5 py-3 font-medium">Longitude</th>
                      <th className="px-5 py-3 font-medium">Incidents</th>
                      <th className="px-5 py-3 font-medium">Top Severity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {hotspots.map((h, i) => (
                      <tr
                        key={i}
                        className="border-b border-[#15181e] last:border-0"
                      >
                        <td className="px-5 py-3 font-mono text-[#8b909c]">
                          {h.lat.toFixed(4)}
                        </td>
                        <td className="px-5 py-3 font-mono text-[#8b909c]">
                          {h.lon.toFixed(4)}
                        </td>
                        <td className="px-5 py-3 font-medium text-[#e7e9ee]">
                          {h.count}
                        </td>
                        <td className="px-5 py-3">
                          <SeverityBadge severity={h.top_severity} />
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
