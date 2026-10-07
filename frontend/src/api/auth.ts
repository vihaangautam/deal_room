import { apiFetch } from "./client"
import type { User } from "./types"

export async function login(email: string, password: string): Promise<void> {
  const form = new URLSearchParams()
  form.set("username", email)
  form.set("password", password)
  await apiFetch("/auth/login", { method: "POST", body: form })
}

export async function logout(): Promise<void> {
  await apiFetch("/auth/logout", { method: "POST" })
}

export async function fetchMe(): Promise<User> {
  return apiFetch<User>("/auth/me")
}

export async function changePassword(
  newPassword: string,
  currentPassword?: string,
): Promise<void> {
  await apiFetch("/auth/change-password", {
    method: "POST",
    body: { new_password: newPassword, current_password: currentPassword },
  })
}
