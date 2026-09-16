"use client";

// Root-level crash fallback (Next.js App Router convention) — catches
// errors in the root layout itself, where error.tsx can't help (it renders
// inside the layout). Deliberately self-contained with inline styles rather
// than relying on globals.css classes, since this is the last line of
// defense if something upstream failed to load.

import { useEffect, useState } from "react";

// This component replaces the root layout, so LocaleProvider does not exist
// here — useLocale() would silently return English. The locale is read
// straight from the same localStorage key the provider writes, with the
// strings inlined for the same reason the styles are: nothing upstream can
// be assumed to have loaded.
const STORAGE_KEY = "gramcare_locale";

const COPY = {
  en: {
    title: "GramCare AI hit a critical error",
    body: "Please reload the app. If you were in the middle of an emergency, call 108 directly.",
    reload: "Reload",
  },
  ta: {
    title: "GramCare AI இல் கடுமையான பிழை ஏற்பட்டது",
    body: "செயலியை மீண்டும் ஏற்றவும். நீங்கள் அவசர நிலையில் இருந்தால், நேரடியாக 108 ஐ அழைக்கவும்.",
    reload: "மீண்டும் ஏற்று",
  },
} as const;

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const [lang, setLang] = useState<keyof typeof COPY>("en");

  useEffect(() => {
    console.error("GramCare AI — critical app error:", error);
  }, [error]);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "ta") setLang("ta");
    } catch {
      // Storage can throw in a private window; English is the safe default.
    }
  }, []);

  const copy = COPY[lang];

  return (
    <html lang={lang}>
      <body style={{ margin: 0, minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "system-ui, sans-serif", background: "#e0e5ec", color: "#2d3748" }}>
        <div style={{ maxWidth: 420, textAlign: "center", padding: 32 }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>⚠️</div>
          <h1 style={{ fontSize: 20, fontWeight: 800, marginBottom: 8 }}>{copy.title}</h1>
          <p style={{ color: "#718096", fontSize: 14, marginBottom: 24 }}>
            {copy.body}
          </p>
          <button
            onClick={reset}
            style={{ padding: "12px 24px", borderRadius: 12, border: "none", background: "#4f46e5", color: "white", fontWeight: 700, cursor: "pointer" }}
          >
            {copy.reload}
          </button>
        </div>
      </body>
    </html>
  );
}
