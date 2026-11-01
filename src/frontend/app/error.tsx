"use client";

import { useEffect, useState } from "react";
import { Button } from "../components/ui";

// Next 16 passes `retry` (older versions called it `reset`); see node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/error.md
export default function Error({ error, retry }: { error: unknown; retry: () => void }) {
  const digest = error instanceof globalThis.Error ? (error as globalThis.Error & { digest?: string }).digest : undefined;
  const [id, setId] = useState(digest || "");
  useEffect(() => {
    const shown = digest || `ui_${Date.now().toString(36)}`; // client errors have no server digest
    setId(shown);
    console.error(`UI error ${shown}`, error);
  }, [error, digest]);
  return (
    <div role="alert" className="mx-auto mt-16 max-w-lg space-y-3 rounded-xl border border-rose-500/40 bg-rose-500/10 p-6" data-testid="error-page">
      <h2 className="text-lg font-bold">This page hit an error</h2>
      <p className="text-sm">Nothing was lost on the server. Try again, and if it keeps happening, report this id: <span className="mono font-semibold">{id}</span></p>
      <Button variant="primary" onClick={() => retry()}>Try again</Button>
    </div>
  );
}
