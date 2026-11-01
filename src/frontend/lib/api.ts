export class ApiError extends Error {
  constructor(message: string, public status: number, public code: string | null = null, public action = "", public errorId = "", public requestId = "") {
    super(message);
  }
}

export async function api<T = any>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...rest } = init;
  const response = await fetch(`/api${path}`, {
    ...rest,
    ...(json !== undefined ? { method: rest.method || "POST", body: JSON.stringify(json), headers: { "Content-Type": "application/json" } } : {}),
  });
  if (response.status === 401 && !path.startsWith("/auth/") && typeof window !== "undefined") {
    window.location.href = "/login";
  }
  if (!response.ok) {
    let detail = response.statusText;
    let body: any = {};
    try {
      body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : body.message || JSON.stringify(body.detail);
    } catch {}
    throw new ApiError(detail || `Request failed (${response.status})`, response.status, body.code ?? null, body.action ?? "", body.error_id ?? "", response.headers.get("X-Request-Id") ?? "");
  }
  if (response.status === 204) return undefined as T;
  return (response.headers.get("content-type") || "").includes("json") ? response.json() : ((await response.text()) as T);
}

export function upload<T = any>(path: string, form: FormData): Promise<T> {
  return api<T>(path, { method: "POST", body: form });
}

export function when(iso?: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
