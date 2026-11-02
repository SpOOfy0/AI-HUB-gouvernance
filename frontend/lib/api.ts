// Client HTTP minimal. Le cookie de session (httpOnly) est envoyé automatiquement par le navigateur.

export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string, public requestId?: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  const res = await fetch(`/api${path}`, {
    ...rest,
    credentials: "same-origin",
    headers: { ...(json !== undefined ? { "Content-Type": "application/json" } : {}), ...headers },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "Erreur inattendue";
    throw new ApiError(res.status, detail, data.code, data.request_id);
  }
  return data as T;
}

export type Role = "ADMIN" | "MANAGER" | "DEVELOPER" | "USER";

export interface CurrentUser {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  department_id: number;
  department_name: string;
}

export interface PublicConfig {
  demo_mode: boolean;
  demo_accounts: { email: string; password: string; role: Role; label: string }[];
}
