import { ReactNode } from "react";

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[#1e222b] bg-[#0c0e12] px-6 py-14 text-center">
      {icon && <div className="mb-3 text-[#8b909c]">{icon}</div>}
      <p className="text-sm font-medium text-[#e7e9ee]">{title}</p>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-[#8b909c]">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-[#ef444433] bg-[#ef44440d] px-5 py-4 text-sm text-[#fca5a5]">
      <p className="font-medium text-[#ef4444]">Could not reach the API</p>
      <p className="mt-1 text-[#fca5a5]/80">{message}</p>
      <p className="mt-2 text-xs text-[#8b909c]">
        Make sure the CityGuard FastAPI backend is running at the configured URL.
      </p>
    </div>
  );
}
