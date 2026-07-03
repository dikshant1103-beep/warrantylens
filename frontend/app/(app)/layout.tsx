"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { ThemeToggle } from "@/components/ThemeToggle";
import { useAuth } from "@/lib/auth";
import type { Role } from "@/lib/types";

const NAV: { href: string; label: string; roles: Role[] }[] = [
  { href: "/dashboard", label: "Dashboard", roles: ["admin", "reviewer", "mechanic"] },
  { href: "/claims", label: "Claims", roles: ["admin", "reviewer", "mechanic"] },
  { href: "/admin/users", label: "Users", roles: ["admin"] },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-500 dark:text-slate-400">
        Loading…
      </div>
    );
  }

  const items = NAV.filter((n) => n.roles.includes(user.role));

  return (
    <div className="flex min-h-screen">
      <aside className="w-60 shrink-0 border-r border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <div className="mb-6 flex items-center gap-2">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-brand text-sm font-bold text-white">
            WL
          </div>
          <div>
            <p className="text-sm font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              WarrantyLens
            </p>
            <p className="text-xs capitalize text-slate-400">{user.role}</p>
          </div>
        </div>
        <nav className="space-y-1">
          {items.map((n) => {
            const active = pathname.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={`block rounded-md px-3 py-2 text-sm transition ${
                  active
                    ? "bg-brand/10 font-medium text-brand-dark dark:bg-brand/20 dark:text-sky-300"
                    : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                }`}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3 dark:border-slate-800 dark:bg-slate-900">
          <span className="text-sm text-slate-500 dark:text-slate-400">{user.email}</span>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <button
              onClick={() => logout()}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Sign out
            </button>
          </div>
        </header>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
