"use client";

// Shown only once the server reports its shared AI quota is spent.
//
// The alternative was the placeholder users were getting: a result card
// that looks like a real assessment — severity HIGH, a department, an
// explanation expander — whose content reads "Unknown (AI Engines
// Unavailable)" at 0% confidence. Saying plainly that the limit is reached,
// and offering a way through it, is more honest than a confident-looking
// empty answer.

import React, { useState } from "react";
import { AlertCircle, ExternalLink } from "lucide-react";
import { useLocale } from "../contexts/LocaleContext";
import { setUserAiKey } from "../lib/aiKey";

interface Props {
  /** Called after a key is saved, so the caller can retry the request. */
  onKeySaved: () => void;
  /** Called when the user says they have no key, to dismiss the prompt. */
  onDismiss: () => void;
}

export default function AiQuotaPrompt({ onKeySaved, onDismiss }: Props) {
  const { t } = useLocale();
  const [entering, setEntering] = useState(false);
  const [value, setValue] = useState("");

  const save = () => {
    if (!value.trim()) return;
    setUserAiKey(value);
    setValue("");
    setEntering(false);
    onKeySaved();
  };

  return (
    <div className="mb-6 rounded-2xl border-2 border-red-500/60 bg-red-500/10 p-4">
      <p className="flex items-center gap-2 font-bold text-red-500">
        <AlertCircle size={18} /> {t("ai_limit_exhausted")}
      </p>

      {!entering ? (
        <>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">
            {t("have_own_api_key")}
          </p>
          <div className="mt-3 flex gap-3">
            <button
              onClick={() => setEntering(true)}
              className="rounded-xl bg-red-500 px-6 py-2 font-bold text-white transition-opacity hover:opacity-90"
            >
              {t("yes")}
            </button>
            <button
              onClick={onDismiss}
              className="rounded-xl border border-red-500/50 px-6 py-2 font-bold text-red-500 transition-colors hover:bg-red-500/10"
            >
              {t("no")}
            </button>
          </div>
        </>
      ) : (
        <>
          <input
            type="password"
            autoFocus
            autoComplete="off"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") save();
            }}
            placeholder={t("paste_api_key")}
            className="mt-3 w-full rounded-xl border border-white/20 bg-white/60 p-3 focus:outline-none focus:ring-2 focus:ring-red-500 dark:bg-black/30"
          />
          <p className="mt-1.5 text-xs text-gray-500">
            {t("api_key_stays_in_browser")}
          </p>
          <a
            href="https://aistudio.google.com/apikey"
            target="_blank"
            rel="noreferrer"
            className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-indigo-500 hover:underline"
          >
            {t("get_a_free_key")} <ExternalLink size={11} />
          </a>
          <div className="mt-3 flex gap-3">
            <button
              onClick={save}
              className="rounded-xl bg-red-500 px-6 py-2 font-bold text-white transition-opacity hover:opacity-90"
            >
              {t("save_and_retry")}
            </button>
            <button
              onClick={() => setEntering(false)}
              className="rounded-xl px-6 py-2 font-bold text-red-500 transition-colors hover:bg-red-500/10"
            >
              {t("cancel")}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
