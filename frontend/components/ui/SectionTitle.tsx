import { ReactNode } from "react";

export function SectionTitle({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4">
      <div>
        <h2 className="text-base font-semibold text-[#e7e9ee]">{title}</h2>
        {subtitle && <p className="mt-0.5 text-sm text-[#8b909c]">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-[#e7e9ee]">
          {title}
        </h1>
        {subtitle && <p className="mt-1 text-sm text-[#8b909c]">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}
