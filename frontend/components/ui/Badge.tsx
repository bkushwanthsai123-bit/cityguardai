import { Severity, Status } from "@/lib/api";

const SEV_STYLES: Record<Severity, { bg: string; text: string; border: string }> = {
  low: { bg: "rgba(34,197,94,0.12)", text: "#22c55e", border: "rgba(34,197,94,0.3)" },
  medium: { bg: "rgba(234,179,8,0.12)", text: "#eab308", border: "rgba(234,179,8,0.3)" },
  high: { bg: "rgba(249,115,22,0.12)", text: "#f97316", border: "rgba(249,115,22,0.3)" },
  critical: { bg: "rgba(239,68,68,0.12)", text: "#ef4444", border: "rgba(239,68,68,0.3)" },
};

const STATUS_STYLES: Record<Status, { bg: string; text: string; border: string; label: string }> = {
  open: { bg: "rgba(59,130,246,0.12)", text: "#60a5fa", border: "rgba(59,130,246,0.3)", label: "Open" },
  in_progress: { bg: "rgba(234,179,8,0.12)", text: "#eab308", border: "rgba(234,179,8,0.3)", label: "In Progress" },
  resolved: { bg: "rgba(34,197,94,0.12)", text: "#22c55e", border: "rgba(34,197,94,0.3)", label: "Resolved" },
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  const s = SEV_STYLES[severity];
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize"
      style={{ background: s.bg, color: s.text, border: `1px solid ${s.border}` }}
    >
      {severity}
    </span>
  );
}

export function StatusBadge({ status }: { status: Status }) {
  const s = STATUS_STYLES[status];
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
      style={{ background: s.bg, color: s.text, border: `1px solid ${s.border}` }}
    >
      {s.label}
    </span>
  );
}

export function Badge({
  children,
  color = "#8b909c",
}: {
  children: React.ReactNode;
  color?: string;
}) {
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
      style={{
        background: `${color}1f`,
        color,
        border: `1px solid ${color}4d`,
      }}
    >
      {children}
    </span>
  );
}
