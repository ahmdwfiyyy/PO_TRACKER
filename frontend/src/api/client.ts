// ---------------------------------------------------------------------------
// Talking to the FastAPI backend (/api is proxied by Vite in dev and by nginx in Docker)
// ---------------------------------------------------------------------------
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

const TOKEN_KEY = "po_tracker_token";
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token: string | null) =>
  token ? localStorage.setItem(TOKEN_KEY, token) : localStorage.removeItem(TOKEN_KEY);

function authHeaders(init?: HeadersInit) {
  const headers = new Headers(init);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

async function failure(res: Response, path: string): Promise<never> {
  const data = await res.json().catch(() => ({}));
  // An expired or invalid session anywhere (except the login form itself) sends the person back to sign in
  if (res.status === 401 && path !== "/api/auth/login") window.dispatchEvent(new Event("auth-expired"));
  const detail = data?.detail;
  const message =
    typeof detail === "string"
      ? detail
      : Array.isArray(detail) && detail[0]?.msg
        ? String(detail[0].msg).replace(/^Value error, /, "")
        : "Please check your inputs";
  throw new ApiError(message, res.status);
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { ...init, headers: authHeaders(init?.headers) });
  if (!res.ok) return failure(res, path);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const sendJson = <T>(path: string, body: unknown, method = "POST") =>
  api<T>(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const MAX_UPLOAD_MB = 10;
export const UPLOAD_ACCEPT = ".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png";

/** Attach a file (PDF/JPG/PNG) to a PO, shipment, receipt or discrepancy. */
export function uploadFile<T>(entityType: string, entityId: number, file: File) {
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    return Promise.reject(new ApiError(`${file.name} is larger than ${MAX_UPLOAD_MB} MB`, 400));
  }
  const form = new FormData();
  form.set("entity_type", entityType);
  form.set("entity_id", String(entityId));
  form.set("file", file);
  return api<T>("/api/attachments", { method: "POST", body: form });
}

/** Upload several files one after another; returns the error messages of any that failed. */
export async function uploadFiles(entityType: string, entityId: number, files: File[]) {
  const errors: string[] = [];
  for (const file of files) {
    try {
      await uploadFile(entityType, entityId, file);
    } catch (err) {
      errors.push(`${file.name}: ${errorText(err)}`);
    }
  }
  return errors;
}

/** Download a file from a protected endpoint (a plain link would not send the login token). */
export async function download(path: string, fallbackName: string) {
  const res = await fetch(path, { headers: authHeaders() });
  if (!res.ok) return failure(res, path);
  const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "")?.[1] ?? fallbackName;
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export const errorText = (err: unknown) => (err instanceof Error ? err.message : "Something went wrong");

/** Build a query string, leaving out empty values. */
export function query(params: Record<string, string | number | boolean | undefined | null>) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  });
  const s = q.toString();
  return s ? `?${s}` : "";
}
