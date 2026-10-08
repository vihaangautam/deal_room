// CLAUDE.md §6.1/6.4: every API call goes through this wrapper. No raw
// fetch() calls in components.

import { useAuthStore } from "@/stores/auth"

// Empty means same-origin, which is how the production image is built:
// nginx proxies the API on the same host, so no absolute URL is needed.
// The ?? "" matters — an undefined VITE_API_URL used to produce
// fetch("undefined/auth/me"), which Vite's SPA fallback answered with
// index.html and a 200, so the app rendered as signed in with no user.
const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ""

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail))
    this.status = status
    this.detail = detail
  }
}

type ApiFetchOptions = Omit<RequestInit, "body"> & { body?: unknown }

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { body, headers, ...rest } = options
  // FormData and URLSearchParams set their own correct Content-Type
  // (multipart boundary / urlencoded) — only JSON bodies need us to set
  // it, and neither should be run through JSON.stringify.
  const isRawBody = body instanceof FormData || body instanceof URLSearchParams

  const init: RequestInit = {
    credentials: "include", // always send the session cookie
    ...rest,
  }
  const effectiveHeaders = isRawBody ? headers : { "Content-Type": "application/json", ...headers }
  if (effectiveHeaders !== undefined) {
    init.headers = effectiveHeaders
  }
  if (isRawBody) {
    init.body = body
  } else if (body !== undefined) {
    init.body = JSON.stringify(body)
  }

  const res = await fetch(`${BASE}${path}`, init)

  if (res.status === 204) {
    return undefined as T
  }

  const isJson = res.headers.get("content-type")?.includes("application/json")
  const payload = isJson ? await res.json().catch(() => undefined) : undefined

  if (!res.ok) {
    // A 12-hour session (PRD F1) means a tab left open overnight wakes up
    // unauthenticated. App.tsx only calls /auth/me on mount, so without
    // this the user sat on a page where every query failed instead of
    // being sent back to the login screen.
    if (res.status === 401) {
      useAuthStore.getState().clear()
    }
    throw new ApiError(res.status, payload?.detail ?? "Couldn't reach the server. Check your connection and try again.")
  }

  return payload as T
}
