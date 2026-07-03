"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api";
import type { Claim, MediaKind } from "@/lib/types";

function kindOf(file: File): MediaKind {
  return file.type.startsWith("video") ? "video" : "image";
}

export default function NewClaimPage() {
  const router = useRouter();
  const [vin, setVin] = useState("");
  const [reason, setReason] = useState("");
  const [narrative, setNarrative] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [claim, setClaim] = useState<Claim | null>(null);
  const [progress, setProgress] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function createDraft(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const c = await api.createClaim({
        vin: vin || null,
        claim_reason: reason || null,
        mechanic_narrative: narrative || null,
      });
      setClaim(c);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create claim");
    } finally {
      setBusy(false);
    }
  }

  async function uploadAndSubmit() {
    if (!claim || files.length === 0) return;
    setError(null);
    setBusy(true);
    try {
      const specs = files.map((f) => ({
        filename: f.name,
        content_type: f.type || "application/octet-stream",
        kind: kindOf(f),
        size: f.size,
      }));
      setProgress("Requesting upload URLs…");
      const { uploads } = await api.requestUploads(claim.id, specs);

      for (let i = 0; i < uploads.length; i++) {
        setProgress(`Uploading ${i + 1}/${uploads.length}: ${files[i].name}`);
        await api.uploadToS3(uploads[i].upload_url, files[i]);
        await api.completeUpload(claim.id, uploads[i].asset_id);
      }

      setProgress("Submitting for processing…");
      await api.submitClaim(claim.id);
      router.push(`/claims/${claim.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
      setProgress("");
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">New inspection claim</h1>

      {!claim && (
        <form onSubmit={createDraft} className="space-y-4 wl-card p-6">
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
            VIN (optional)
            <input
              value={vin}
              onChange={(e) => setVin(e.target.value.toUpperCase())}
              maxLength={17}
              className="wl-input mt-1 uppercase"
            />
          </label>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
            Claim reason
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="wl-input mt-1"
            />
          </label>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
            Mechanic narrative
            <textarea
              value={narrative}
              onChange={(e) => setNarrative(e.target.value)}
              rows={4}
              className="wl-input mt-1"
            />
          </label>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
          >
            {busy ? "Creating…" : "Create draft"}
          </button>
        </form>
      )}

      {claim && (
        <div className="space-y-4 wl-card p-6">
          <p className="text-sm text-slate-600 dark:text-slate-300">
            Draft <strong>{claim.claim_number}</strong> created. Add evidence (video + images),
            then submit.
          </p>
          <input
            type="file"
            multiple
            accept="video/*,image/*"
            onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
            className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-brand file:px-3 file:py-1.5 file:text-white dark:text-slate-300"
          />
          {files.length > 0 && (
            <ul className="text-sm text-slate-600 dark:text-slate-300">
              {files.map((f) => (
                <li key={f.name}>
                  {kindOf(f) === "video" ? "🎬" : "🖼️"} {f.name} ({Math.round(f.size / 1024)} KB)
                </li>
              ))}
            </ul>
          )}
          {progress && <p className="text-sm text-brand-dark">{progress}</p>}
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            onClick={uploadAndSubmit}
            disabled={busy || files.length === 0}
            className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
          >
            {busy ? "Working…" : "Upload & submit"}
          </button>
        </div>
      )}
    </div>
  );
}
