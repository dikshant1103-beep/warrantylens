"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AnimatedNumber } from "@/components/AnimatedNumber";
import { RiskMeter } from "@/components/RiskMeter";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const ICONS: Record<string, React.ReactNode> = {
  total: <path d="M4 4h12v12H4z M7 8h6 M7 11h6" />,
  pending: <path d="M10 5v5l3 2 M10 17a7 7 0 100-14 7 7 0 000 14z" />,
  processing: <path d="M10 3v3 M10 14v3 M3 10h3 M14 10h3 M5 5l2 2 M13 13l2 2" />,
  risk: <path d="M10 3l8 14H2L10 3z M10 9v3 M10 15h.01" />,
};

function StatCard({
  label, value, icon, tone, delay, suffix = "", decimals = 0, hint,
}: {
  label: string; value: number | null | undefined; icon: string;
  tone: string; delay: number; suffix?: string; decimals?: number; hint?: string;
}) {
  return (
    <div
      className="wl-card animate-rise p-5 transition duration-200 hover:-translate-y-0.5 hover:shadow-md"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-start justify-between">
        <p className="text-sm wl-muted">{label}</p>
        <span className={`grid h-8 w-8 place-items-center rounded-lg ${tone}`}>
          <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor"
               strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            {ICONS[icon]}
          </svg>
        </span>
      </div>
      <p className="mt-2 text-3xl font-semibold tabular-nums text-slate-900 dark:text-slate-100">
        <AnimatedNumber value={value} decimals={decimals} suffix={suffix} />
      </p>
      {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
    </div>
  );
}

function RiskBar({ dist }: { dist: { low: number; elevated: number; high: number } }) {
  const total = dist.low + dist.elevated + dist.high || 1;
  const [grown, setGrown] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setGrown(true));
    return () => cancelAnimationFrame(id);
  }, []);
  const seg = [
    { n: dist.low, c: "bg-emerald-500", l: "low", t: "text-emerald-600 dark:text-emerald-400" },
    { n: dist.elevated, c: "bg-amber-500", l: "elevated", t: "text-amber-600 dark:text-amber-400" },
    { n: dist.high, c: "bg-red-500", l: "high", t: "text-red-600 dark:text-red-400" },
  ];
  return (
    <div>
      <div className="flex h-4 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        {seg.map((s) => (
          <div
            key={s.l}
            className={`${s.c} transition-[width] duration-1000 ease-out`}
            style={{ width: grown ? `${(s.n / total) * 100}%` : "0%" }}
          />
        ))}
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2">
        {seg.map((s) => (
          <div key={s.l} className="rounded-lg bg-slate-50 p-2 text-center dark:bg-slate-800">
            <p className={`text-xl font-semibold tabular-nums ${s.t}`}>
              <AnimatedNumber value={s.n} />
            </p>
            <p className="text-xs capitalize wl-muted">{s.l}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function Gauge({ score, count }: { score: number | null; count: number }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const [offset, setOffset] = useState(c);
  const pct = score ?? 0;
  const color = score == null ? "#cbd5e1" : pct >= 80 ? "#10b981" : pct >= 50 ? "#f59e0b" : "#ef4444";
  useEffect(() => {
    const id = requestAnimationFrame(() => setOffset(c - (pct / 100) * c));
    return () => cancelAnimationFrame(id);
  }, [pct, c]);
  return (
    <div className="flex flex-col items-center">
      <div className="relative h-36 w-36">
        <svg className="h-36 w-36 -rotate-90" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r={r} fill="none" strokeWidth="12"
                  className="stroke-slate-200 dark:stroke-slate-700" />
          <circle
            cx="60" cy="60" r={r} fill="none" stroke={color} strokeWidth="12"
            strokeLinecap="round" strokeDasharray={c} strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset 1.1s cubic-bezier(0.22,1,0.36,1)" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-semibold tabular-nums text-slate-900 dark:text-slate-100">
            <AnimatedNumber value={score} />
          </span>
          <span className="text-xs text-slate-400">/ 100</span>
        </div>
      </div>
      <p className="mt-2 text-xs wl-muted">{count} claims scored</p>
    </div>
  );
}

function Card({ children, className = "", delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  return (
    <div className={`wl-card animate-rise p-5 ${className}`} style={{ animationDelay: `${delay}ms` }}>
      {children}
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const overview = useQuery({ queryKey: ["dash-overview"], queryFn: api.dashOverview });
  const risk = useQuery({ queryKey: ["dash-risk"], queryFn: api.dashRisk });
  const comp = useQuery({ queryKey: ["dash-comp"], queryFn: api.dashCompleteness });
  const queue = useQuery({ queryKey: ["dash-queue"], queryFn: api.dashQueue });

  const o = overview.data;
  const highRisk = risk.data?.high;
  const heading = "text-sm font-semibold text-slate-700 dark:text-slate-200";

  return (
    <div className="space-y-6">
      <div className="animate-fade">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          Welcome, {user?.full_name}
        </h1>
        <p className="text-sm wl-muted">Claims overview for your service centre.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total claims" value={o?.total} icon="total" tone="bg-sky-50 text-sky-600 dark:bg-sky-500/10 dark:text-sky-400" delay={0} />
        <StatCard label="Pending review" value={o?.pending_review} icon="pending" tone="bg-violet-50 text-violet-600 dark:bg-violet-500/10 dark:text-violet-400" delay={80} />
        <StatCard label="Processing" value={o?.processing} icon="processing" tone="bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400" delay={160} />
        <StatCard label="High-risk flags" value={highRisk} icon="risk" tone="bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400" delay={240} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2" delay={120}>
          <h2 className={`mb-4 ${heading}`}>Risk distribution</h2>
          {risk.data ? <RiskBar dist={risk.data} /> : <p className="text-sm text-slate-400">No scored claims yet.</p>}
        </Card>

        <Card delay={200}>
          <h2 className={`mb-3 ${heading}`}>Avg. completeness</h2>
          <Gauge score={comp.data?.average ?? null} count={comp.data?.scored_claims ?? 0} />
        </Card>
      </div>

      <Card delay={260}>
        <div className="mb-3 flex items-center justify-between">
          <h2 className={heading}>Reviewer queue · highest risk first</h2>
          <Link href="/claims" className="text-xs font-medium text-brand-dark hover:underline dark:text-sky-400">
            View all →
          </Link>
        </div>
        {queue.data && queue.data.length > 0 ? (
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {queue.data.slice(0, 6).map((c, i) => (
              <li
                key={c.id}
                className="animate-rise flex items-center justify-between gap-4 py-2.5"
                style={{ animationDelay: `${300 + i * 60}ms` }}
              >
                <Link href={`/claims/${c.id}`} className="text-sm font-medium text-brand-dark hover:underline dark:text-sky-400">
                  {c.claim_number}
                </Link>
                <span className="hidden flex-1 text-xs text-slate-400 sm:block">{c.vin ?? "—"}</span>
                <div className="w-36">
                  <RiskMeter score={c.risk_score} />
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-400">Queue is empty.</p>
        )}
      </Card>

      <div className="animate-fade rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-300">
        <strong>Advisory only.</strong> WarrantyLens surfaces evidence and risk
        indicators to assist reviewers. It never decides or alleges fraud — every
        final warranty decision is made by a human.
      </div>
    </div>
  );
}
