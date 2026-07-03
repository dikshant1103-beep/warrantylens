"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import type { ClaimStatus } from "@/lib/types";

function Spark({ values, color }: { values: number[]; color: string }) {
  const pts = values.filter((v) => typeof v === "number");
  if (pts.length < 2) return null;
  const min = Math.min(...pts);
  const max = Math.max(...pts);
  const range = max - min || 1;
  const w = 240;
  const h = 40;
  const d = pts.map((v, i) => `${(i / (pts.length - 1)) * w},${h - ((v - min) / range) * h}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-10 w-full" preserveAspectRatio="none">
      <polyline points={d} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}

function leanTone(lean: string) {
  if (lean === "supports_warranty") return "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300";
  if (lean === "suggests_misuse" || lean === "external_cause") return "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300";
  return "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300";
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="wl-card p-4">
      <h2 className="mb-3 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">{title}</h2>
      {children}
    </section>
  );
}

export default function PassportPage() {
  const { vin } = useParams<{ vin: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["passport", vin],
    queryFn: () => api.getPassport(vin),
  });

  if (isLoading) return <p className="text-sm text-slate-500">Loading…</p>;
  if (error || !data) return <p className="text-sm text-red-600">Failed to load passport</p>;

  const tel = data.telemetry;

  return (
    <div className="space-y-5">
      <div>
        <Link href="/vehicles" className="text-xs text-brand-dark hover:underline dark:text-sky-400">← Vehicles</Link>
        <h1 className="mt-1 font-mono text-2xl font-semibold text-slate-900 dark:text-slate-100">{data.vin}</h1>
        <p className="text-sm wl-muted">
          {data.vehicle ? [data.vehicle.make, data.vehicle.model].filter(Boolean).join(" ") || "Vehicle digital passport" : "Vehicle digital passport"}
          {data.vehicle?.profile ? ` · telemetry profile: ${data.vehicle.profile}` : ""}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Telemetry history">
          {tel?.summary?.days ? (
            <>
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${leanTone(tel.leaning)}`}>
                {tel.leaning.replace(/_/g, " ")}
              </span>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{tel.note}</p>
              <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                <div className="rounded-lg bg-slate-50 p-2 dark:bg-slate-800">
                  <p className="text-xs text-slate-400">Odometer</p>
                  <p className="font-semibold text-slate-800 dark:text-slate-200">{Math.round(tel.summary.odometer_km ?? 0)} km</p>
                </div>
                <div className="rounded-lg bg-slate-50 p-2 dark:bg-slate-800">
                  <p className="text-xs text-slate-400">Harsh events</p>
                  <p className="font-semibold text-slate-800 dark:text-slate-200">{tel.summary.harsh_events ?? 0}</p>
                </div>
              </div>
              <div className="mt-3">
                <p className="mb-1 text-xs text-slate-400">Motor temp trend</p>
                <Spark values={tel.series.map((p) => p.motor ?? 0)} color="#ef4444" />
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-400">No telemetry on record.</p>
          )}
        </Card>

        <Card title="Registered parts (manufacture)">
          {data.parts.length > 0 ? (
            <ul className="space-y-1 text-sm">
              {data.parts.map((p) => (
                <li key={p.serial} className="flex items-center justify-between">
                  <span className="text-slate-600 dark:text-slate-300">{p.component_code ?? "part"}</span>
                  <span className="font-mono text-slate-800 dark:text-slate-200">{p.serial}</span>
                  <span className={`text-xs ${p.is_active ? "text-emerald-600" : "text-slate-400 line-through"}`}>
                    {p.is_active ? "active" : "removed"}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-400">No parts registered.</p>
          )}
        </Card>
      </div>

      <Card title="Battery health history">
        {data.battery_reports.length > 0 ? (
          <ul className="space-y-1 text-sm">
            {data.battery_reports.map((b) => (
              <li key={b.id} className="flex items-center justify-between">
                <span className="text-slate-600 dark:text-slate-300">
                  SoH {b.soh_percent ?? "—"}% · RUL {b.rul_cycles ?? "—"} cyc
                </span>
                {b.warranty_leaning && (
                  <span className={`rounded-full px-2 py-0.5 text-xs ${leanTone(b.warranty_leaning)}`}>
                    {b.warranty_leaning.replace(/_/g, " ")}
                  </span>
                )}
                <span className="text-xs text-slate-400">{new Date(b.created_at).toLocaleDateString()}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-400">No battery reports attached.</p>
        )}
      </Card>

      <Card title={`Claims history (${data.claims.length})`}>
        {data.claims.length > 0 ? (
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {data.claims.map((c) => (
              <li key={c.id} className="flex items-center justify-between py-2 text-sm">
                <Link href={`/claims/${c.id}`} className="text-brand-dark hover:underline dark:text-sky-400">
                  {c.claim_number}
                </Link>
                <StatusBadge status={c.status as ClaimStatus} />
                <span className="text-slate-500 dark:text-slate-400">risk {c.risk_score ?? "—"}</span>
                <span className="text-xs text-slate-400">{new Date(c.created_at).toLocaleDateString()}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-400">No claims for this vehicle.</p>
        )}
      </Card>

      {data.part_events.length > 0 && (
        <Card title="Part lifecycle log">
          <ul className="space-y-0.5 text-xs text-slate-500 dark:text-slate-400">
            {data.part_events.map((e, i) => (
              <li key={i}>
                <span className="font-mono">{e.serial}</span> · {e.event_type.replace(/_/g, " ")} ·{" "}
                {new Date(e.created_at).toLocaleDateString()}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
