"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { RiskMeter } from "@/components/RiskMeter";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Decision, Detection } from "@/lib/types";

const PROCESSING = new Set(["queued", "processing"]);
const DECISIONS: Decision[] = ["approved", "rejected", "needs_more_evidence", "escalated"];

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
  const reportQ = useQuery({ queryKey: ["report", id], queryFn: () => api.getReport(id), enabled: aiReady });
  const reviewsQ = useQuery({ queryKey: ["reviews", id], queryFn: () => api.getReviews(id), enabled: aiReady });

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
          <p className="text-sm text-slate-500 dark:text-slate-400">VIN: {claim.vin ?? "—"}</p>
        </div>
        <StatusBadge status={claim.status} />
      </div>

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
