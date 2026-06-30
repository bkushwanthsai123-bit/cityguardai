import { ReactNode } from "react";
import { Card } from "./Card";

export function KpiCard({
  label,
  value,
  icon,
  accent = "#3b82f6",
  delta,
}: {
  label: string;
  value: ReactNode;
  icon?: ReactNode;
  accent?: string;
  delta?: string;
}) {
  return (
    <Card className="flex items-start justify-between">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-[#8b909c]">
          {label}
        </p>
        <p className="mt-2 text-3xl font-semibold text-[#e7e9ee]">{value}</p>
        {delta && <p className="mt-1 text-xs text-[#8b909c]">{delta}</p>}
      </div>
      {icon && (
        <div
          className="flex h-10 w-10 items-center justify-center rounded-lg"
          style={{ background: `${accent}1f`, color: accent }}
        >
          {icon}
        </div>
      )}
    </Card>
  );
}
