import { ReactNode } from "react";

export function Card({
  children,
  className = "",
  padded = true,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border border-[#1e222b] bg-[#111317] shadow-sm shadow-black/30 ${
        padded ? "p-5" : ""
      } ${className}`}
    >
      {children}
    </div>
  );
}
