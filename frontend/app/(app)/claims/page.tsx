"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";

export default function ClaimsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["claims"],
    queryFn: () => api.listClaims(),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Claims</h1>
        <Link
          href="/claims/new"
          className="rounded-md bg-brand px-3 py-2 text-sm font-medium text-white hover:bg-brand-dark"
        >
          + New claim
        </Link>
      </div>

      {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {error && (
        <p className="text-sm text-red-600">
          {error instanceof Error ? error.message : "Failed to load"}
        </p>
      )}

      {data && data.items.length === 0 && (
        <p className="text-sm text-slate-500">No claims yet. Create one to get started.</p>
      )}

      {data && data.items.length > 0 && (
        <div className="wl-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              <tr>
                <th className="px-4 py-2 font-medium">Claim #</th>
                <th className="px-4 py-2 font-medium">VIN</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Risk</th>
                <th className="px-4 py-2 font-medium">Created</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((c) => (
                <tr key={c.id} className="border-t border-slate-100 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50">
                  <td className="px-4 py-2">
                    <Link href={`/claims/${c.id}`} className="text-brand-dark hover:underline dark:text-sky-400">
                      {c.claim_number}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-slate-600 dark:text-slate-300">{c.vin ?? "—"}</td>
                  <td className="px-4 py-2">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="px-4 py-2 text-slate-700 dark:text-slate-300">{c.risk_score ?? "—"}</td>
                  <td className="px-4 py-2 text-slate-500 dark:text-slate-400">
                    {new Date(c.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
