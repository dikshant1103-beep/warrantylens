"use client";

import { useEffect, useState } from "react";

function band(score: number) {
  if (score < 33) return { label: "low", color: "bg-emerald-500", text: "text-emerald-700" };
  if (score < 66) return { label: "elevated", color: "bg-amber-500", text: "text-amber-700" };
  return { label: "high", color: "bg-red-500", text: "text-red-700" };
}

export function RiskMeter({ score }: { score: number | null | undefined }) {
  const [w, setW] = useState(0);
  const target = score ?? 0;

  useEffect(() => {
    const id = requestAnimationFrame(() => setW(Math.min(target, 100)));
    return () => cancelAnimationFrame(id);
  }, [target]);

  if (score === null || score === undefined) {
    return <span className="text-sm text-slate-400">—</span>;
  }
  const b = band(score);
  return (
    <div className="w-full">
      <div className="flex items-center justify-between text-sm">
        <span className={`font-semibold ${b.text}`}>{score.toFixed(0)}/100</span>
        <span className={`text-xs uppercase ${b.text}`}>{b.label}</span>
      </div>
      <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full ${b.color} transition-[width] duration-700 ease-out`}
          style={{ width: `${w}%` }}
        />
      </div>
    </div>
  );
}
