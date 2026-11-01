"use client";

import { useEffect, useState } from "react";

// Replaces the root layout, so it brings its own html, body, and styles.
export default function GlobalError({ error, retry }: { error: unknown; retry: () => void }) {
  const digest = error instanceof globalThis.Error ? (error as globalThis.Error & { digest?: string }).digest : undefined;
  const [id, setId] = useState(digest || "");
  useEffect(() => {
    const shown = digest || `ui_${Date.now().toString(36)}`; // client errors have no server digest
    setId(shown);
    console.error(`UI error ${shown}`, error);
  }, [error, digest]);
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", background: "#030712", color: "#f1f5f9", margin: 0 }}>
        <div role="alert" style={{ maxWidth: 480, margin: "64px auto", padding: 24, border: "1px solid #f43f5e66", borderRadius: 12, background: "#f43f5e1a" }}>
          <h2 style={{ marginTop: 0 }}>The application hit an error</h2>
          <p>Nothing was lost on the server. Try again, and if it keeps happening, report this id: <b style={{ fontFamily: "monospace" }}>{id}</b></p>
          <button onClick={() => retry()} style={{ padding: "8px 16px", borderRadius: 8, border: 0, background: "#6366f1", color: "white", fontWeight: 600, cursor: "pointer" }}>Try again</button>
        </div>
      </body>
    </html>
  );
}
