"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { Claim, MediaKind } from "@/lib/types";

const IMAGE_EXT = /\.(jpe?g|png|webp|heic|bmp|gif)$/i;
const VIDEO_EXT = /\.(mp4|mov|mkv|webm|avi|m4v)$/i;

function isMedia(f: File): boolean {
  return (
    f.type.startsWith("image/") ||
    f.type.startsWith("video/") ||
    IMAGE_EXT.test(f.name) ||
    VIDEO_EXT.test(f.name)
  );
}

function kindOf(file: File): MediaKind {
  if (file.type.startsWith("video/") || VIDEO_EXT.test(file.name)) return "video";
  return "image";
}

function contentType(f: File): string {
  if (f.type) return f.type;
  if (VIDEO_EXT.test(f.name)) return "video/mp4";
  return "image/jpeg";
}

export default function NewClaimPage() {
  const router = useRouter();
  const [vin, setVin] = useState("");
  const [reason, setReason] = useState("");
  const [narrative, setNarrative] = useState("");
  const [removedSerial, setRemovedSerial] = useState("");
  const [replacementSerial, setReplacementSerial] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [claim, setClaim] = useState<Claim | null>(null);
  const [progress, setProgress] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const folderRef = useRef<HTMLInputElement>(null);

  // webkitdirectory isn't a standard React attribute — set it on the DOM node.
  useEffect(() => {
    if (folderRef.current) {
      folderRef.current.setAttribute("webkitdirectory", "");
      folderRef.current.setAttribute("directory", "");
    }
  }, [claim]);

  function addFiles(selected: FileList | null) {
    const incoming = Array.from(selected ?? []).filter(isMedia);
    setFiles((prev) => {
      const seen = new Set(prev.map((f) => f.name + f.size));
      const merged = [...prev];
      for (const f of incoming) {
        const key = f.name + f.size;
        if (!seen.has(key)) {
          seen.add(key);
          merged.push(f);
        }
      }
      return merged;
    });
  }

  async function createDraft(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const c = await api.createClaim({
        vin: vin || null,
        claim_reason: reason || null,
        mechanic_narrative: narrative || null,
        removed_serial: removedSerial || null,
        replacement_serial: replacementSerial || null,
      });
      setClaim(c);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create claim");
    } finally {
      setBusy(false);
    }
  }

  async function uploadAndSubmit() {
    if (!claim || files.length === 0 || busy) return;
    setError(null);
    setBusy(true);
    try {
      const specs = files.map((f) => ({
        filename: f.name,
        content_type: contentType(f),
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

      setProgress("Submitting for AI analysis…");
      await api.submitClaim(claim.id);
      router.push(`/claims/${claim.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
      setProgress("");
    }
  }

  const imgCount = files.filter((f) => kindOf(f) === "image").length;
  const vidCount = files.filter((f) => kindOf(f) === "video").length;

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
            <input value={reason} onChange={(e) => setReason(e.target.value)} className="wl-input mt-1" />
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

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
              Removed part serial
              <input
                value={removedSerial}
                onChange={(e) => setRemovedSerial(e.target.value.toUpperCase())}
                placeholder="serial of the defective part"
                className="wl-input mt-1 uppercase"
              />
            </label>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
              Replacement part serial
              <input
                value={replacementSerial}
                onChange={(e) => setReplacementSerial(e.target.value.toUpperCase())}
                placeholder="serial of the new part"
                className="wl-input mt-1 uppercase"
              />
            </label>
          </div>
          <p className="text-xs text-slate-400">
            Serials are cross-checked against the vehicle&apos;s registered parts to flag
            swapped, reused, or unproven components.
          </p>

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
        <div className="space-y-5 wl-card p-6">
          <p className="text-sm text-slate-600 dark:text-slate-300">
            Draft <strong>{claim.claim_number}</strong> created. Add evidence — pick
            individual files or a whole folder — then submit for AI analysis.
          </p>

          {/* Two upload modes */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="flex cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed border-slate-300 px-4 py-6 text-center transition hover:border-brand hover:bg-brand/5 dark:border-slate-700">
              <span className="text-2xl">🖼️</span>
              <span className="text-sm font-medium text-slate-700 dark:text-slate-200">Select files</span>
              <span className="text-xs text-slate-400">images or videos</span>
              <input
                type="file"
                multiple
                accept="video/*,image/*"
                onChange={(e) => addFiles(e.target.files)}
                className="hidden"
              />
            </label>

            <label className="flex cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed border-slate-300 px-4 py-6 text-center transition hover:border-brand hover:bg-brand/5 dark:border-slate-700">
              <span className="text-2xl">📁</span>
              <span className="text-sm font-medium text-slate-700 dark:text-slate-200">Upload a folder</span>
              <span className="text-xs text-slate-400">e.g. the demo_images folder</span>
              <input
                ref={folderRef}
                type="file"
                multiple
                onChange={(e) => addFiles(e.target.files)}
                className="hidden"
              />
            </label>
          </div>

          {files.length > 0 && (
            <div className="rounded-lg border border-slate-200 dark:border-slate-700">
              <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2 text-sm dark:border-slate-800">
                <span className="font-medium text-slate-700 dark:text-slate-200">
                  {files.length} file{files.length > 1 ? "s" : ""} ready
                  <span className="ml-2 text-xs text-slate-400">
                    {imgCount} image{imgCount !== 1 ? "s" : ""} · {vidCount} video{vidCount !== 1 ? "s" : ""}
                  </span>
                </span>
                <button
                  onClick={() => setFiles([])}
                  disabled={busy}
                  className="text-xs text-slate-500 hover:text-red-600"
                >
                  Clear
                </button>
              </div>
              <ul className="max-h-48 overflow-auto px-3 py-2 text-sm text-slate-600 dark:text-slate-300">
                {files.map((f, i) => (
                  <li key={f.name + i} className="flex justify-between py-0.5">
                    <span className="truncate">{kindOf(f) === "video" ? "🎬" : "🖼️"} {f.name}</span>
                    <span className="ml-3 flex-none text-xs text-slate-400">{Math.round(f.size / 1024)} KB</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {progress && (
            <div className="flex items-center gap-2 text-sm text-brand-dark dark:text-sky-400">
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
              </svg>
              {progress}
            </div>
          )}
          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            onClick={uploadAndSubmit}
            disabled={busy || files.length === 0}
            className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
          >
            {busy ? "Working…" : `Upload & analyze (${files.length})`}
          </button>
        </div>
      )}
    </div>
  );
}
