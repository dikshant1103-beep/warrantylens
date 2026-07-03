"use client";

import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("wl-theme", next ? "dark" : "light");
  }

  return (
    <button
      onClick={toggle}
      aria-label="Toggle theme"
      title={dark ? "Switch to light" : "Switch to dark"}
      className="grid h-9 w-9 place-items-center rounded-lg border border-slate-200 text-slate-600 transition hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
    >
      {dark ? (
        // sun
        <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path d="M10 4a1 1 0 011 1V4a1 1 0 11-2 0 1 1 0 011 0zm0 11a3 3 0 100-6 3 3 0 000 6zm7-5a1 1 0 110 2h-1a1 1 0 110-2h1zM4 10a1 1 0 01-1 1H2a1 1 0 110-2h1a1 1 0 011 1zm11.66 5.66a1 1 0 01-1.42 0l-.7-.7a1 1 0 011.42-1.42l.7.7a1 1 0 010 1.42zM6.46 6.46a1 1 0 01-1.42 0l-.7-.7A1 1 0 015.76 4.34l.7.7a1 1 0 010 1.42zm9.2-2.12a1 1 0 010 1.42l-.7.7a1 1 0 11-1.42-1.42l.7-.7a1 1 0 011.42 0zM6.46 13.54a1 1 0 010 1.42l-.7.7a1 1 0 01-1.42-1.42l.7-.7a1 1 0 011.42 0zM10 16a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1z" />
        </svg>
      ) : (
        // moon
        <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
        </svg>
      )}
    </button>
  );
}
