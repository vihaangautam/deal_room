import { useQuery } from "@tanstack/react-query"
import { apiFetch } from "./client"
import type { AccessLevel } from "./types"

// Folder id -> the current user's own access level. Admins get
// 'contribute' for every folder (see backend/app/routers/auth.py).
export function useMyPermissions() {
  return useQuery({
    queryKey: ["my-permissions"],
    queryFn: () => apiFetch<Record<string, AccessLevel>>("/auth/my-permissions"),
  })
}
