"use client";

import { useState } from "react";

import { useAuth } from "@/lib/auth";

const DEMO = { email: "admin@demo.warrantylens.io", password: "Admin12345!" };

function Logo({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className="grid h-9 w-9 place-items-center rounded-lg bg-brand font-bold text-white shadow-sm">
        WL
      </div>
      <span className="text-lg font-semibold tracking-tight">WarrantyLens</span>
    </div>
  );
}

function Feature({ title, desc }: { title: string; desc: string }) {
  return (
    <li className="flex gap-3">
      <svg className="mt-0.5 h-5 w-5 flex-none text-brand" viewBox="0 0 20 20" fill="currentColor">
        <path
          fillRule="evenodd"
          d="M16.7 5.3a1 1 0 010 1.4l-7.5 7.5a1 1 0 01-1.4 0L3.3 9.7a1 1 0 011.4-1.4l3.1 3.1 6.8-6.8a1 1 0 011.4 0z"
          clipRule="evenodd"
        />
      </svg>
      <div>
        <p className="text-sm font-medium text-white">{title}</p>
        <p className="text-sm text-slate-400">{desc}</p>
      </div>
    </li>
  );
}

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState(DEMO.email);
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      {/* Brand panel */}
      <section className="relative hidden flex-col justify-between overflow-hidden bg-slate-900 p-12 text-white lg:flex">
        <div
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            background:
              "radial-gradient(600px circle at 20% 20%, rgba(14,165,233,0.25), transparent 60%)," +
              "radial-gradient(500px circle at 80% 80%, rgba(16,185,129,0.18), transparent 55%)",
          }}
        />
        <div className="relative">
          <Logo />
          <h1 className="mt-16 max-w-md text-3xl font-semibold leading-tight">
            AI-assisted EV warranty inspections
          </h1>
          <p className="mt-3 max-w-md text-slate-400">
            Verify evidence faster and surface suspicious claims — with damage
            detection, VIN/serial reading, and explainable risk scoring.
          </p>
          <ul className="mt-10 space-y-5">
            <Feature title="Automated evidence analysis" desc="Frames, damage, VIN & narration from every upload." />
            <Feature title="Explainable risk scoring" desc="Every score links back to the evidence behind it." />
            <Feature title="Human-in-the-loop" desc="Advisory only — reviewers make the final call." />
          </ul>
        </div>
        <p className="relative text-xs text-slate-500">
          © {new Date().getFullYear()} WarrantyLens · Advisory tool — never an automated decision.
        </p>
      </section>

      {/* Form panel */}
      <section className="flex items-center justify-center bg-slate-50 p-6 dark:bg-slate-950">
        <div className="w-full max-w-sm">
          <Logo className="mb-8 text-slate-900 dark:text-slate-100 lg:hidden" />

          <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
            Welcome back
          </h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Sign in to your inspection workspace.
          </p>

          <form onSubmit={onSubmit} className="mt-8 space-y-4">
            <div>
              <label htmlFor="email" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="wl-input"
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={show ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="wl-input pr-16"
                />
                <button
                  type="button"
                  onClick={() => setShow((s) => !s)}
                  className="absolute inset-y-0 right-0 px-3 text-xs font-medium text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                >
                  {show ? "Hide" : "Show"}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300">
                <svg className="mt-0.5 h-4 w-4 flex-none" viewBox="0 0 20 20" fill="currentColor">
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM9 9a1 1 0 112 0v4a1 1 0 11-2 0V9zm1-4a1 1 0 100 2 1 1 0 000-2z"
                    clipRule="evenodd"
                  />
                </svg>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-brand-dark disabled:opacity-60"
            >
              {busy && (
                <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                </svg>
              )}
              {busy ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <button
            type="button"
            onClick={() => {
              setEmail(DEMO.email);
              setPassword(DEMO.password);
            }}
            className="mt-4 w-full rounded-lg border border-dashed border-slate-300 px-3 py-2 text-xs text-slate-500 transition hover:border-brand hover:text-brand-dark dark:border-slate-700 dark:text-slate-400 dark:hover:border-brand dark:hover:text-sky-400"
          >
            Use demo credentials
          </button>
        </div>
      </section>
    </main>
  );
}
