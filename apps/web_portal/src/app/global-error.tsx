"use client";

// Root-level crash fallback (Next.js App Router convention) — catches
// errors in the root layout itself, where error.tsx can't help (it renders
// inside the layout). Deliberately self-contained with inline styles rather
// than relying on globals.css classes, since this is the last line of
// defense if something upstream failed to load.

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error("GramCare AI — critical app error:", error);
  }, [error]);

  return (
    <html lang="en">
      <body style={{ margin: 0, minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "system-ui, sans-serif", background: "#e0e5ec", color: "#2d3748" }}>
        <div style={{ maxWidth: 420, textAlign: "center", padding: 32 }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>⚠️</div>
          <h1 style={{ fontSize: 20, fontWeight: 800, marginBottom: 8 }}>GramCare AI hit a critical error</h1>
          <p style={{ color: "#718096", fontSize: 14, marginBottom: 24 }}>
            Please reload the app. If you were in the middle of an emergency, call 108 directly.
          </p>
          <button
            onClick={reset}
            style={{ padding: "12px 24px", borderRadius: 12, border: "none", background: "#4f46e5", color: "white", fontWeight: 700, cursor: "pointer" }}
          >
            Reload
          </button>
        </div>
      </body>
    </html>
  );
}
