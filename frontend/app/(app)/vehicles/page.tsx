"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { api } from "@/lib/api";

export default function VehiclesPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["vehicles"],
    queryFn: () => api.listVehicles(),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Vehicles</h1>
      <p className="text-sm wl-muted">
        Per-VIN digital passport — manufacture parts, telemetry history, claims and battery health.
      </p>

      {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {error && <p className="text-sm text-red-600">{error instanceof Error ? error.message : "Failed"}</p>}

      {data && data.length === 0 && <p className="text-sm text-slate-500">No vehicles yet.</p>}
      {data && data.length > 0 && (
        <div className="wl-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              <tr>
                <th className="px-4 py-2 font-medium">VIN</th>
                <th className="px-4 py-2 font-medium">Make / Model</th>
                <th className="px-4 py-2 font-medium">Telemetry profile</th>
              </tr>
            </thead>
            <tbody>
              {data.map((v) => (
                <tr key={v.vin} className="border-t border-slate-100 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50">
                  <td className="px-4 py-2">
                    <Link href={`/vehicles/${encodeURIComponent(v.vin)}`} className="font-mono text-brand-dark hover:underline dark:text-sky-400">
                      {v.vin}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-slate-600 dark:text-slate-300">
                    {[v.make, v.model].filter(Boolean).join(" ") || "—"}
                  </td>
                  <td className="px-4 py-2 text-slate-500 dark:text-slate-400">{v.profile ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
