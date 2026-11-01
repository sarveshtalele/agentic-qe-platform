"use client";

import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Field, inputClass } from "./ui";

/** Only models this person may use. Blank follows the normal order: the agent's model, then the account default, then the system default. */
export function ModelPicker({ value, onChange, label = "Model", compact = false }: { value: string; onChange: (model: string) => void; label?: string; compact?: boolean }) {
  const [options, setOptions] = useState<{ models: string[]; default: string } | null>(null);
  useEffect(() => {
    api("/settings/models").then(setOptions).catch(() => setOptions({ models: [], default: "" }));
  }, []);
  if (!options) return null;
  if (!options.models.length) return <p role="alert" className="text-xs text-rose-500">No model is allowed for your account. Ask your administrator to tick one.</p>;
  const select = (
    <select aria-label={label} name="run-model" className={`${inputClass} ${compact ? "!w-auto !py-1 text-xs" : ""}`} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">Default{options.default ? ` (${options.default})` : ""}</option>
      {options.models.map((m) => <option key={m} value={m}>{m}</option>)}
    </select>
  );
  return compact ? select : <Field label={label} hint="Leave on Default to follow the agent and account settings.">{select}</Field>;
}
