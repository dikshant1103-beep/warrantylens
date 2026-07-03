"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

export default function UsersPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["users"],
    queryFn: () => api.listUsers(),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Users</h1>

      {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {error && (
        <p className="text-sm text-red-600">
          {error instanceof Error ? error.message : "Failed to load"}
        </p>
      )}

      {data && (
        <div className="wl-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              <tr>
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Email</th>
                <th className="px-4 py-2 font-medium">Role</th>
                <th className="px-4 py-2 font-medium">Active</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((u) => (
                <tr key={u.id} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="px-4 py-2 text-slate-800 dark:text-slate-200">{u.full_name}</td>
                  <td className="px-4 py-2 text-slate-600 dark:text-slate-400">{u.email}</td>
                  <td className="px-4 py-2">
                    <span className="rounded-full bg-brand/10 px-2 py-0.5 text-xs text-brand-dark dark:bg-brand/20 dark:text-sky-300">
                      {u.role}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-slate-700 dark:text-slate-300">{u.is_active ? "Yes" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
