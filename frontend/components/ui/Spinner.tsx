export function Spinner({ size = 18 }: { size?: number }) {
  return (
    <span
      className="inline-block animate-spin rounded-full border-2 border-[#2a3040] border-t-[#3b82f6]"
      style={{ width: size, height: size }}
      aria-label="Loading"
    />
  );
}

export function LoadingBlock({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-sm text-[#8b909c]">
      <Spinner />
      {label}
    </div>
  );
}
