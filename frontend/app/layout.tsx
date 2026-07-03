import type { Metadata } from "next";

import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "WarrantyLens",
  description: "AI EV Warranty Inspection Assistant — advisory only.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Apply the saved (or system) theme before paint to avoid a flash of wrong theme.
  const themeScript = `(function(){try{var t=localStorage.getItem('wl-theme');var d=t?t==='dark':window.matchMedia('(prefers-color-scheme:dark)').matches;if(d)document.documentElement.classList.add('dark');}catch(e){}})();`;
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
