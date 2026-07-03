"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { RiskMeter } from "@/components/RiskMeter";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Decision, Detection } from "@/lib/types";

const PROCESSING = new Set(["queued", "processing"]);
const DECISIONS: Decision[] = ["approved", "rejected", "needs_more_evidence", "escalated"];

function Sparkline({ values, color }: { values: number[]; color: string }) {
  const pts = values.filter((v) => typeof v === "number");
  if (pts.length < 2) return null;
  const min = Math.min(...pts);
  const max = Math.max(...pts);
  const range = max - min || 1;
  const w = 240;
  const h = 40;
  const d = pts
    .map((v, i) => `${(i / (pts.length - 1)) * w},${h - ((v - min) / range) * h}`)
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-10 w-full" preserveAspectRatio="none">
      <polyline points={d} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}

function leanTone(lean: string) {
  if (lean === "supports_warranty")
    return "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300";
  if (lean === "suggests_misuse" || lean === "external_cause")
    return "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300";
  return "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300";
}

function FrameWithBoxes({ url, boxes }: { url: string; boxes: Detection[] }) {
  return (
    <div className="relative inline-block">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={url} alt="frame" className="aspect-video rounded border border-slate-200 object-cover" />
      {boxes.filter((b) => b.bbox && b.defect_label).map((b) => (
        <div
          key={b.id}
          className="absolute border-2 border-red-500"
          style={{
            left: `${b.bbox!.x * 100}%`,
            top: `${b.bbox!.y * 100}%`,
            width: `${b.bbox!.w * 100}%`,
            height: `${b.bbox!.h * 100}%`,
          }}
          title={`${b.defect_label} ${(b.confidence * 100).toFixed(0)}%`}
        />
      ))}
    </div>
  );
}

export default function ClaimDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const qc = useQueryClient();
  const [decision, setDecision] = useState<Decision>("approved");
  const [notes, setNotes] = useState("");

  const claimQ = useQuery({
    queryKey: ["claim", id],
    queryFn: () => api.getClaim(id),
    refetchInterval: (q) => (q.state.data && PROCESSING.has(q.state.data.status) ? 3000 : false),
  });
  const aiReady = !!claimQ.data && !PROCESSING.has(claimQ.data.status);

  const statusQ = useQuery({
    queryKey: ["claim-status", id],
    queryFn: () => api.getStatus(id),
    refetchInterval: (q) => (q.state.data && PROCESSING.has(q.state.data.status) ? 3000 : false),
  });
  const evidenceQ = useQuery({ queryKey: ["evidence", id, claimQ.data?.status], queryFn: () => api.getEvidence(id), enabled: !!claimQ.data });
  const detectionsQ = useQuery({ queryKey: ["detections", id], queryFn: () => api.getDetections(id), enabled: aiReady });
  const transcriptQ = useQuery({ queryKey: ["transcript", id], queryFn: () => api.getTranscript(id), enabled: aiReady });
  const ocrQ = useQuery({ queryKey: ["ocr", id], queryFn: () => api.getOcr(id), enabled: aiReady });
  const completenessQ = useQuery({ queryKey: ["completeness", id], queryFn: () => api.getCompleteness(id), enabled: aiReady });
  const riskQ = useQuery({ queryKey: ["risk", id], queryFn: () => api.getRisk(id), enabled: aiReady });
  const verdictQ = useQuery({ queryKey: ["verdict", id], queryFn: () => api.getVerdict(id), enabled: aiReady });
  const reportQ = useQuery({ queryKey: ["report", id], queryFn: () => api.getReport(id), enabled: aiReady });
  const reviewsQ = useQuery({ queryKey: ["reviews", id], queryFn: () => api.getReviews(id), enabled: aiReady });
  const partEventsQ = useQuery({ queryKey: ["part-events", id], queryFn: () => api.getPartEvents(id), enabled: aiReady });
  const batteryQ = useQuery({ queryKey: ["battery", id], queryFn: () => api.getBatteryReport(id), enabled: aiReady });

  const telemetryQ = useQuery({
    queryKey: ["telemetry", claimQ.data?.vin],
    queryFn: () => api.getTelemetry(claimQ.data!.vin!),
    enabled: aiReady && !!claimQ.data?.vin,
  });

  const [batteryErr, setBatteryErr] = useState<string | null>(null);
  const batteryMut = useMutation({
    mutationFn: async (file: File) => {
      const text = await file.text();
      const json = JSON.parse(text);
      return api.attachBatteryReport(id, json);
    },
    onSuccess: () => {
      setBatteryErr(null);
      qc.invalidateQueries({ queryKey: ["battery", id] });
      qc.invalidateQueries({ queryKey: ["risk", id] });
      qc.invalidateQueries({ queryKey: ["report", id] });
      qc.invalidateQueries({ queryKey: ["verdict", id] });
    },
    onError: (e) => setBatteryErr(e instanceof Error ? e.message : "Failed to attach report"),
  });

  const reviewMut = useMutation({
    mutationFn: () => api.submitReview(id, decision, notes),
    onSuccess: () => {
      setNotes("");
      qc.invalidateQueries({ queryKey: ["claim", id] });
      qc.invalidateQueries({ queryKey: ["reviews", id] });
    },
  });

  const claim = claimQ.data;
  if (claimQ.isLoading) return <p className="text-sm text-slate-500 dark:text-slate-400">Loading…</p>;
  if (!claim) return <p className="text-sm text-red-600">Claim not found</p>;

  const canReview = user && (user.role === "reviewer" || user.role === "admin");
  const boxesByFrame = (frameId: string) =>
    (detectionsQ.data ?? []).filter((d) => d.frame_id === frameId);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">{claim.claim_number}</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            VIN:{" "}
            {claim.vin ? (
              <Link href={`/vehicles/${encodeURIComponent(claim.vin)}`} className="text-brand-dark hover:underline dark:text-sky-400">
                {claim.vin}
              </Link>
            ) : "—"}
          </p>
        </div>
        <StatusBadge status={claim.status} />
      </div>

      {/* Unified advisory verdict */}
      {aiReady && verdictQ.data && (() => {
        const v = verdictQ.data;
        const tone =
          v.verdict === "likely_manufacturing_defect"
            ? "border-emerald-300 bg-emerald-50 dark:border-emerald-900/50 dark:bg-emerald-950/40"
            : v.verdict === "likely_misuse_or_external"
            ? "border-red-300 bg-red-50 dark:border-red-900/50 dark:bg-red-950/40"
            : "border-slate-300 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/50";
        const head =
          v.verdict === "likely_manufacturing_defect"
            ? "text-emerald-800 dark:text-emerald-300"
            : v.verdict === "likely_misuse_or_external"
            ? "text-red-800 dark:text-red-300"
            : "text-slate-700 dark:text-slate-200";
        return (
          <section className={`rounded-xl border p-4 ${tone}`}>
            <div className="flex items-center justify-between">
              <h2 className={`text-lg font-semibold ${head}`}>
                Advisory verdict: {v.verdict.replace(/_/g, " ")}
              </h2>
              <span className="text-xs wl-muted">confidence {(v.confidence * 100).toFixed(0)}%</span>
            </div>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{v.rationale}</p>
            {v.integrity_concern && (
              <p className="mt-2 rounded-md bg-amber-100 px-2 py-1 text-xs text-amber-800 dark:bg-amber-500/15 dark:text-amber-300">
                ⚠ Serial-number integrity concern — verify claimed parts independently.
              </p>
            )}
            {v.sources.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {v.sources.map((s) => (
                  <span
                    key={s.source}
                    className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                    title={s.note ?? ""}
                  >
                    {s.source}: {s.leaning.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            )}
          </section>
        );
      })()}

      {/* Scores + report */}
      {aiReady && (
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="wl-card p-4">
            <h3 className="mb-2 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">Risk (advisory)</h3>
            <RiskMeter score={riskQ.data?.score ?? null} />
            {riskQ.data?.rationale && <p className="mt-2 text-xs text-slate-500">{riskQ.data.rationale}</p>}
          </div>
          <div className="wl-card p-4">
            <h3 className="mb-2 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">Completeness</h3>
            <p className="text-2xl font-semibold text-slate-900 dark:text-slate-100">{completenessQ.data ? `${completenessQ.data.score}/100` : "—"}</p>
            {completenessQ.data && completenessQ.data.missing.length > 0 && (
              <ul className="mt-2 list-disc pl-4 text-xs text-orange-700">
                {completenessQ.data.missing.map((m) => <li key={m}>{m}</li>)}
              </ul>
            )}
          </div>
          <div className="wl-card p-4">
            <h3 className="mb-2 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">Report</h3>
            {reportQ.data ? (
              <div className="space-y-1 text-sm">
                {reportQ.data.pdf_url && <a className="block text-brand-dark hover:underline dark:text-sky-400" href={reportQ.data.pdf_url} target="_blank" rel="noreferrer">Download PDF</a>}
                {reportQ.data.html_url && <a className="block text-brand-dark hover:underline dark:text-sky-400" href={reportQ.data.html_url} target="_blank" rel="noreferrer">View HTML</a>}
                <p className="text-xs text-slate-400">v{reportQ.data.version}</p>
              </div>
            ) : (
              <p className="text-sm text-slate-400">No report yet.</p>
            )}
          </div>
        </section>
      )}

      {/* Risk factors */}
      {aiReady && riskQ.data && riskQ.data.factors.length > 0 && (
        <section className="wl-card p-4">
          <h3 className="mb-2 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">Risk factors (evidence-linked)</h3>
          <table className="w-full text-sm text-slate-700 dark:text-slate-300">
            <thead className="text-left text-slate-500 dark:text-slate-400">
              <tr><th className="py-1">Indicator</th><th>Source</th><th>Conf.</th><th>Contribution</th><th>Refs</th></tr>
            </thead>
            <tbody>
              {riskQ.data.factors.map((f, i) => (
                <tr key={i} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="py-1">{f.indicator.replace(/_/g, " ")}</td>
                  <td className="text-slate-500 dark:text-slate-400">{f.source}</td>
                  <td>{(f.confidence * 100).toFixed(0)}%</td>
                  <td>{f.contribution}</td>
                  <td className="text-slate-400">{f.evidence_refs.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* Parts & serials */}
      {(claim.removed_serial || claim.replacement_serial) && (
        <section className="wl-card p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
            Parts &amp; serials (anti swap-and-sell)
          </h3>
          <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
            <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800">
              <p className="text-xs text-slate-400">Removed (claimed defective)</p>
              <p className="font-mono text-slate-800 dark:text-slate-200">{claim.removed_serial ?? "—"}</p>
            </div>
            <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800">
              <p className="text-xs text-slate-400">Replacement installed</p>
              <p className="font-mono text-slate-800 dark:text-slate-200">{claim.replacement_serial ?? "—"}</p>
            </div>
          </div>
          {/* serial flags surfaced from the risk engine */}
          {riskQ.data && riskQ.data.factors.filter((f) => f.source === "serial").length > 0 && (
            <ul className="mt-3 space-y-1 text-sm">
              {riskQ.data.factors.filter((f) => f.source === "serial").map((f, i) => (
                <li key={i} className="flex items-start gap-2 text-amber-700 dark:text-amber-400">
                  <span className="mt-0.5">⚠</span>
                  <span>
                    <b>{f.indicator.replace(/_/g, " ")}</b>
                    {f.note ? ` — ${f.note}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {partEventsQ.data && partEventsQ.data.length > 0 && (
            <div className="mt-3 border-t border-slate-100 pt-3 dark:border-slate-800">
              <p className="mb-1 text-xs text-slate-400">Lifecycle log</p>
              <ul className="space-y-0.5 text-xs text-slate-500 dark:text-slate-400">
                {partEventsQ.data.map((e) => (
                  <li key={e.id}>
                    <span className="font-mono">{e.serial}</span> · {e.event_type.replace(/_/g, " ")}
                    {e.vin ? ` · VIN ${e.vin}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {/* Battery health (BatteryOS) */}
      {aiReady && (
        <section className="wl-card p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
              Battery health (from BatteryOS)
            </h3>
            <label className="cursor-pointer text-xs font-medium text-brand-dark hover:underline dark:text-sky-400">
              {batteryMut.isPending ? "Attaching…" : batteryQ.data ? "Replace report" : "Attach battery report"}
              <input
                type="file"
                accept="application/json,.json"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) batteryMut.mutate(f);
                }}
              />
            </label>
          </div>
          {batteryErr && <p className="mb-2 text-sm text-red-600">{batteryErr}</p>}

          {batteryQ.data ? (
            <>
              {(() => {
                const b = batteryQ.data;
                const lean = b.warranty_leaning;
                const tone =
                  lean === "supports_warranty"
                    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300"
                    : lean === "suggests_misuse"
                    ? "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300"
                    : "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300";
                return (
                  <div className="mb-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${tone}`}>
                      {(lean ?? "inconclusive").replace(/_/g, " ")}
                    </span>
                    {b.assessment_note && (
                      <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{b.assessment_note}</p>
                    )}
                  </div>
                );
              })()}
              <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                {[
                  ["SoH", batteryQ.data.soh_percent != null ? `${batteryQ.data.soh_percent}%` : "—"],
                  ["RUL", batteryQ.data.rul_cycles != null ? `${batteryQ.data.rul_cycles} cyc` : "—"],
                  ["Capacity fade", batteryQ.data.capacity_fade_percent != null ? `${batteryQ.data.capacity_fade_percent}%` : "—"],
                  ["Chemistry", batteryQ.data.chemistry ?? "—"],
                ].map(([k, v]) => (
                  <div key={k} className="rounded-lg bg-slate-50 p-2 dark:bg-slate-800">
                    <p className="text-xs text-slate-400">{k}</p>
                    <p className="font-semibold text-slate-800 dark:text-slate-200">{v}</p>
                  </div>
                ))}
              </div>
              {batteryQ.data.abuse_indicators && batteryQ.data.abuse_indicators.length > 0 && (
                <div className="mt-3">
                  <p className="text-xs text-slate-400">Abuse indicators</p>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {batteryQ.data.abuse_indicators.map((a) => (
                      <span key={a} className="rounded-full bg-red-50 px-2 py-0.5 text-xs text-red-700 dark:bg-red-500/15 dark:text-red-300">
                        {a.replace(/_/g, " ")}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {batteryQ.data.faults && batteryQ.data.faults.length > 0 && (
                <ul className="mt-3 space-y-0.5 text-xs text-slate-500 dark:text-slate-400">
                  {batteryQ.data.faults.map((f, i) => (
                    <li key={i}>
                      <span className="font-mono">{f.code}</span> {f.desc} ({f.severity})
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <p className="text-sm text-slate-400">
              No battery report attached. Upload a BatteryOS report (JSON) to factor battery
              health into the assessment.
            </p>
          )}
        </section>
      )}

      {/* Vehicle telemetry history (non-battery) */}
      {aiReady && claim.vin && (
        <section className="wl-card p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
            Vehicle telemetry history
          </h3>
          {telemetryQ.data && telemetryQ.data.summary?.days ? (
            <>
              <div className="mb-3">
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${leanTone(telemetryQ.data.leaning)}`}>
                  {telemetryQ.data.leaning.replace(/_/g, " ")}
                </span>
                <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{telemetryQ.data.note}</p>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                {[
                  ["Days logged", telemetryQ.data.summary.days],
                  ["Odometer", `${Math.round(telemetryQ.data.summary.odometer_km ?? 0)} km`],
                  ["Harsh events", telemetryQ.data.summary.harsh_events ?? 0],
                  ["Over-temp days (motor)", telemetryQ.data.summary.motor_overtemp_days ?? 0],
                ].map(([k, v]) => (
                  <div key={String(k)} className="rounded-lg bg-slate-50 p-2 dark:bg-slate-800">
                    <p className="text-xs text-slate-400">{k}</p>
                    <p className="font-semibold text-slate-800 dark:text-slate-200">{v}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <p className="mb-1 text-xs text-slate-400">Motor temp trend (°C avg)</p>
                  <Sparkline values={telemetryQ.data.series.map((p) => p.motor ?? 0)} color="#ef4444" />
                </div>
                <div>
                  <p className="mb-1 text-xs text-slate-400">Controller temp trend (°C avg)</p>
                  <Sparkline values={telemetryQ.data.series.map((p) => p.controller ?? 0)} color="#0ea5e9" />
                </div>
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-400">
              No telemetry history on record for VIN {claim.vin}.
            </p>
          )}
        </section>
      )}

      {/* Pipeline */}
      <section className="wl-card p-4">
        <h3 className="mb-2 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">Pipeline</h3>
        {statusQ.data?.processing_error && <p className="mb-2 text-sm text-red-600">{statusQ.data.processing_error}</p>}
        {statusQ.data && statusQ.data.stages.length > 0 ? (
          <ul className="grid grid-cols-2 gap-1 text-sm sm:grid-cols-3">
            {statusQ.data.stages.map((s, i) => (
              <li key={i} className="flex justify-between rounded bg-slate-50 px-2 py-1 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                <span>{s.stage.replace(/_/g, " ")}</span>
                <span className="text-slate-500 dark:text-slate-400">{s.status}</span>
              </li>
            ))}
          </ul>
        ) : <p className="text-sm text-slate-500">No processing yet.</p>}
      </section>

      {/* Evidence + bbox overlay */}
      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-200">Evidence</h2>
        {evidenceQ.data && (
          <>
            <div className="mb-4 flex flex-wrap gap-3">
              {evidenceQ.data.media.map((m) =>
                m.kind === "image" ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img key={m.id} src={m.url ?? ""} alt="evidence" className="h-32 rounded-md border border-slate-200 object-cover" />
                ) : (
                  <video key={m.id} src={m.url ?? ""} controls className="h-32 rounded-md border border-slate-200" />
                ),
              )}
            </div>
            {evidenceQ.data.frames.length > 0 && (
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
                {evidenceQ.data.frames.map((f) => (
                  <FrameWithBoxes key={f.id} url={f.url ?? ""} boxes={boxesByFrame(f.id)} />
                ))}
              </div>
            )}
          </>
        )}
      </section>

      {/* AI extras */}
      {aiReady && (
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="wl-card p-4">
            <h3 className="mb-2 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">Extracted identifiers</h3>
            {ocrQ.data && ocrQ.data.filter((o) => o.field_type === "vin" || o.field_type === "serial").length > 0 ? (
              <ul className="space-y-1 text-sm">
                {ocrQ.data.filter((o) => o.field_type === "vin" || o.field_type === "serial").map((o) => (
                  <li key={o.id} className="flex justify-between">
                    <span className="uppercase text-slate-500 dark:text-slate-400">{o.field_type}</span>
                    <span className="font-mono text-slate-800 dark:text-slate-200">{o.normalized_value}</span>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-slate-400">No VIN/serial extracted.</p>}
          </div>
          <div className="wl-card p-4">
            <h3 className="mb-2 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">Narration</h3>
            <p className="text-sm text-slate-600 dark:text-slate-300">
              {transcriptQ.data && transcriptQ.data.length > 0
                ? transcriptQ.data.map((t) => t.full_text).join(" ") || claim.mechanic_narrative
                : claim.mechanic_narrative ?? "—"}
            </p>
          </div>
        </section>
      )}

      {/* Reviewer decision */}
      {aiReady && canReview && (
        <section className="wl-card p-4">
          <h3 className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-200">Reviewer decision</h3>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm text-slate-700 dark:text-slate-300">
              Decision
              <select
                value={decision}
                onChange={(e) => setDecision(e.target.value as Decision)}
                className="wl-input mt-1 block"
              >
                {DECISIONS.map((d) => <option key={d} value={d}>{d.replace(/_/g, " ")}</option>)}
              </select>
            </label>
            <label className="flex-1 text-sm text-slate-700 dark:text-slate-300">
              Notes
              <input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="wl-input mt-1 block"
              />
            </label>
            <button
              onClick={() => reviewMut.mutate()}
              disabled={reviewMut.isPending}
              className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
            >
              {reviewMut.isPending ? "Saving…" : "Record decision"}
            </button>
          </div>
          {reviewsQ.data && reviewsQ.data.length > 0 && (
            <ul className="mt-4 space-y-1 text-sm">
              {reviewsQ.data.map((r) => (
                <li key={r.id} className="text-slate-600 dark:text-slate-300">
                  <b>{r.decision.replace(/_/g, " ")}</b> — {r.notes || "no notes"}{" "}
                  <span className="text-slate-400">({new Date(r.created_at).toLocaleString()})</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-300">
        Advisory only — evidence and risk indicators assist the reviewer. The final
        warranty decision is always a human&apos;s.
      </div>
    </div>
  );
}
