import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "./client"
import { toast } from "@/components/ui/toast"
import type { ArchiveItem, AuditLogItem, PermissionMatrixEntry, UserAdmin } from "./types"

export function useAdminUsers() {
  return useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => apiFetch<UserAdmin[]>("/admin/users"),
  })
}

export function useCreateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      display_name: string
      email: string
      role: "admin" | "member"
      can_approve: boolean
      folder_levels: Record<string, string>
    }) => apiFetch<{ id: string; display_name: string; email: string; temporary_password: string }>(
      "/admin/users",
      { method: "POST", body },
    ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "users"] }),
  })
}

export function useUpdateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      userId,
      ...body
    }: {
      userId: string
      role?: "admin" | "member"
      can_approve?: boolean
      is_active?: boolean
    }) => apiFetch<UserAdmin>(`/admin/users/${userId}`, { method: "PATCH", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "users"] }),
  })
}

export function useResetPassword() {
  return useMutation({
    mutationFn: (userId: string) =>
      apiFetch<{ temporary_password: string }>(`/admin/users/${userId}/reset-password`, {
        method: "POST",
      }),
  })
}

export function usePermissionMatrix() {
  return useQuery({
    queryKey: ["admin", "permissions"],
    queryFn: () => apiFetch<PermissionMatrixEntry[]>("/admin/permissions"),
  })
}

export function useSetPermission() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, folderId, accessLevel }: { userId: string; folderId: string; accessLevel: string }) =>
      apiFetch<PermissionMatrixEntry>(`/admin/permissions/${userId}/${folderId}`, {
        method: "PUT",
        body: { access_level: accessLevel },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "permissions"] })
      toast("Access updated.")
    },
  })
}

export function useArchive() {
  return useQuery({
    queryKey: ["admin", "archive"],
    queryFn: () => apiFetch<ArchiveItem[]>("/admin/archive"),
  })
}

export function useRestoreDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (docId: string) =>
      apiFetch<{ status: string }>(`/admin/archive/${docId}/restore`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "archive"] })
      // The file reappears in its deal's document list.
      qc.invalidateQueries({ queryKey: ["documents"] })
      toast("File restored to its folder.")
    },
  })
}

export function usePurgeDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (docId: string) =>
      apiFetch<{ status: string }>(`/admin/archive/${docId}/purge`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "archive"] })
      qc.invalidateQueries({ queryKey: ["documents"] })
      // No Undo on this one — DESIGN.md §5.13 calls it "destructive and
      // final", and the object really is gone.
      toast("File deleted permanently.")
    },
  })
}

export interface AuditFilters {
  dealId?: string
  actorId?: string
  action?: string
  since?: string
  until?: string
  limit?: number
}

export function useAuditActions() {
  return useQuery({
    queryKey: ["admin", "audit-actions"],
    queryFn: () => apiFetch<string[]>("/admin/audit-log/actions"),
  })
}

export function useAuditLog(filters?: AuditFilters) {
  const query = new URLSearchParams()
  if (filters?.dealId) query.set("deal_id", filters.dealId)
  if (filters?.action) query.set("action", filters.action)
  if (filters?.since) query.set("since", filters.since)
  if (filters?.until) query.set("until", filters.until)
  if (filters?.actorId) query.set("actor_id", filters.actorId)
  if (filters?.limit) query.set("limit", String(filters.limit))
  const qs = query.toString()

  return useQuery({
    // The whole filter set, not a couple of its fields: keying on part
    // of it hands back the previous filter's rows from cache, which looks
    // exactly like the filters not working.
    queryKey: ["admin", "audit-log", qs],
    queryFn: () => apiFetch<AuditLogItem[]>(`/admin/audit-log${qs ? `?${qs}` : ""}`),
  })
}
