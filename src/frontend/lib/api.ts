export class ApiError extends Error {
  constructor(message: string, public status: number) {
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
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {}
    throw new ApiError(detail || `Request failed (${response.status})`, response.status);
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
