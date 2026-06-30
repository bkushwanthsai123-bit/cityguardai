"use client";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  PieChart,
  Pie,
  AreaChart,
  Area,
  Legend,
} from "recharts";
import { SEVERITY_COLORS, Severity } from "@/lib/api";

const AXIS = { fill: "#8b909c", fontSize: 12 };
const GRID = "#1e222b";

const tooltipStyle = {
  background: "#111317",
  border: "1px solid #1e222b",
  borderRadius: 10,
  color: "#e7e9ee",
  fontSize: 12,
};

export interface ChartDatum {
  name: string;
  value: number;
}

export function recordToData(
  rec: Record<string, number> | undefined,
  order?: string[]
): ChartDatum[] {
  if (!rec) return [];
  const entries = Object.entries(rec);
  if (order) {
    entries.sort((a, b) => {
      const ia = order.indexOf(a[0]);
      const ib = order.indexOf(b[0]);
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    });
  }
  return entries.map(([name, value]) => ({ name, value }));
}

export function SimpleBar({
  data,
  color = "#3b82f6",
  height = 240,
  severityColored = false,
}: {
  data: ChartDatum[];
  color?: string;
  height?: number;
  severityColored?: boolean;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis
          dataKey="name"
          tick={AXIS}
          tickLine={false}
          axisLine={{ stroke: GRID }}
          interval={0}
          angle={data.length > 4 ? -20 : 0}
          textAnchor={data.length > 4 ? "end" : "middle"}
          height={data.length > 4 ? 56 : 30}
        />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
        <Tooltip
          contentStyle={tooltipStyle}
          cursor={{ fill: "rgba(255,255,255,0.04)" }}
        />
        <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={56}>
          {data.map((d, i) => (
            <Cell
              key={i}
              fill={
                severityColored
                  ? SEVERITY_COLORS[d.name as Severity] ?? color
                  : color
              }
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function SeverityPie({
  data,
  height = 260,
}: {
  data: ChartDatum[];
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={95}
          paddingAngle={2}
          stroke="#111317"
        >
          {data.map((d, i) => (
            <Cell
              key={i}
              fill={SEVERITY_COLORS[d.name as Severity] ?? "#6366f1"}
            />
          ))}
        </Pie>
        <Tooltip contentStyle={tooltipStyle} />
        <Legend
          wrapperStyle={{ fontSize: 12, color: "#8b909c" }}
          formatter={(v) => <span style={{ color: "#8b909c" }}>{v}</span>}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function TrendArea({
  data,
  height = 260,
}: {
  data: { date: string; count: number }[];
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <defs>
          <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.4} />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis
          dataKey="date"
          tick={AXIS}
          tickLine={false}
          axisLine={{ stroke: GRID }}
          minTickGap={24}
        />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Area
          type="monotone"
          dataKey="count"
          stroke="#3b82f6"
          strokeWidth={2}
          fill="url(#trendFill)"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
