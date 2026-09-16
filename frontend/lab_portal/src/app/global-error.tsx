"use client";

import { useEffect, useState } from "react";

import { LOCALE_STORAGE_KEY } from "../contexts/LocaleContext";

// This replaces the root layout, so LocaleProvider does not exist here and
// useLocale() would silently return English. The strings are inlined for
// the same reason the styles are: nothing upstream is guaranteed to have
// loaded.
const COPY = {
  en: {
    title: "GramCare Lab Portal hit a critical error",
    body: "Please reload the app.",
    reload: "Reload",
  },
  ta: {
    title: "GramCare ஆய்வகப் போர்டலில் கடுமையான பிழை ஏற்பட்டது",
    body: "செயலியை மீண்டும் ஏற்றவும்.",
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
    console.error("GramCare Lab Portal — critical app error:", error);
  }, [error]);

  useEffect(() => {
    try {
      if (localStorage.getItem(LOCALE_STORAGE_KEY) === "ta") setLang("ta");
    } catch {
      // Storage throws in a private window; English is the safe default.
    }
  }, []);

  const copy = COPY[lang];

  return (
    <html lang={lang}>
      <body style={{ margin: 0, minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "system-ui, sans-serif", background: "#e0e5ec", color: "#2d3748" }}>
        <div style={{ maxWidth: 420, textAlign: "center", padding: 32 }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>⚠️</div>
          <h1 style={{ fontSize: 20, fontWeight: 800, marginBottom: 8 }}>{copy.title}</h1>
          <p style={{ color: "#718096", fontSize: 14, marginBottom: 24 }}>{copy.body}</p>
          <button
            onClick={reset}
            style={{ padding: "12px 24px", borderRadius: 12, border: "none", background: "#7c3aed", color: "white", fontWeight: 700, cursor: "pointer" }}
          >
            {copy.reload}
          </button>
        </div>
      </body>
    </html>
  );
}
