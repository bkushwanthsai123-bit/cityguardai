"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Zap,
  LayoutGrid,
  Map as MapIcon,
  ClipboardList,
  BarChart3,
  Video,
  Code2,
  LogOut,
} from "lucide-react";

const NAV = [
  { label: "Dashboard", href: "/", icon: LayoutGrid },
  { label: "Map View", href: "/map", icon: MapIcon },
  { label: "Incidents", href: "/incidents", icon: ClipboardList },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
  { label: "Detect", href: "/detect", icon: Video },
  { label: "API Docs", href: "/api-docs", icon: Code2 },
];

interface ModelMetrics {
  map50: number | null;
  f1: number | null;
}

function fmtPct(v: number | null): string {
  if (v === null || v === undefined) return "pending";
  const pct = v <= 1 ? v * 100 : v;
  return `${pct.toFixed(1)}%`;
}

export default function Sidebar() {
  const pathname = usePathname();
  const [metrics, setMetrics] = useState<ModelMetrics>({ map50: null, f1: null });

  useEffect(() => {
    fetch("/model-metrics.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setMetrics(d))
      .catch(() => {});
  }, []);

  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-[272px] flex-col border-r border-[#1e222b] bg-[#0c0e12]">
      {/* Brand */}
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="brand-gradient flex h-10 w-10 items-center justify-center rounded-lg shadow-lg shadow-blue-500/20">
          <Zap className="h-5 w-5 text-white" strokeWidth={2.5} />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-semibold text-white">CityGuard AI</p>
          <p className="text-xs text-[#8b909c]">Smart City System</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 pb-4">
        <p className="px-3 pb-2 pt-3 text-[10px] font-semibold uppercase tracking-wider text-[#8b909c]">
          Navigation
        </p>
        <ul className="space-y-1">
          {NAV.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                    active
                      ? "bg-[#1a2230] font-medium text-[#60a5fa]"
                      : "text-[#8b909c] hover:bg-[#15181e] hover:text-[#e7e9ee]"
                  }`}
                >
                  {active && (
                    <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r bg-[#3b82f6]" />
                  )}
                  <Icon className="h-[18px] w-[18px] shrink-0" />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>

        {/* Model card chip */}
        <div className="mt-6 rounded-lg border border-[#1e222b] bg-[#111317] p-3">
          <p className="text-xs font-semibold text-[#e7e9ee]">
            YOLOv8 + Llama 3.2
          </p>
          <p className="mt-1 font-mono text-[11px] leading-relaxed text-[#8b909c]">
            mAP@0.5: {fmtPct(metrics.map50)} · F1: {fmtPct(metrics.f1)}
          </p>
        </div>
      </nav>

      {/* User footer */}
      <div className="border-t border-[#1e222b] px-3 py-3">
        <div className="flex items-center gap-3 rounded-lg px-2 py-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-[#3b82f6] to-[#6366f1] text-sm font-semibold text-white">
            D
          </div>
          <div className="min-w-0 leading-tight">
            <p className="truncate text-sm text-[#e7e9ee]">Demo User</p>
            <p className="truncate text-xs text-[#8b909c]">demo@cityguard.ai</p>
          </div>
        </div>
        <button
          type="button"
          className="mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-[#8b909c] transition-colors hover:bg-[#15181e] hover:text-[#e7e9ee]"
        >
          <LogOut className="h-[18px] w-[18px]" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
