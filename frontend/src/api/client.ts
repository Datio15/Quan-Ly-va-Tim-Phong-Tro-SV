// Client gọi /api/v1 (SPEC 10). Token JWT lưu trong localStorage.
const BASE = "/api/v1";
const TOKEN_KEY = "phongtro.token";

export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, unknown>;
  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* trình duyệt chặn storage: bỏ qua */
  }
}

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

type Query = Record<string, string | number | boolean | undefined | null | (string | number)[]>;

export function toQuery(params: Query): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "" || v === false) continue;
    if (Array.isArray(v)) v.forEach((x) => sp.append(k, String(x)));
    else sp.append(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

interface RequestOpts {
  method?: string;
  body?: unknown;
  query?: Query;
  form?: FormData;
}

export async function apiRaw(path: string, opts: RequestOpts = {}): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}${opts.query ? toQuery(opts.query) : ""}`, {
      method: opts.method || (body ? "POST" : "GET"),
      headers,
      body,
    });
  } catch {
    throw new ApiError(0, "NETWORK", "Không kết nối được máy chủ");
  }
  if (!res.ok) {
    let code = "HTTP_ERROR";
    let message = `Lỗi ${res.status}`;
    let details: Record<string, unknown> = {};
    try {
      const data = await res.json();
      if (data?.error) {
        code = data.error.code;
        message = data.error.message;
        details = data.error.details || {};
      }
    } catch {
      /* không phải JSON */
    }
    if (res.status === 401 && token) onUnauthorized?.();
    throw new ApiError(res.status, code, message, details);
  }
  return res;
}

export async function api<T = unknown>(path: string, opts: RequestOpts = {}): Promise<T> {
  const res = await apiRaw(path, opts);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const fields = (err.details?.fields as { loc: string[]; msg: string }[] | undefined) || [];
    if (fields.length) return `${err.message}: ${fields.map((f) => `${f.loc.slice(1).join(".")} – ${f.msg}`).join("; ")}`;
    return err.message;
  }
  return err instanceof Error ? err.message : "Đã có lỗi xảy ra";
}
