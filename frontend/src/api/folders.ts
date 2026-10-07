import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch, ApiError } from "./client"
import type { Folder } from "./types"

export function useFolders() {
  return useQuery({
    queryKey: ["folders"],
    queryFn: () => apiFetch<Folder[]>("/folders"),
  })
}

export function useCreateFolder() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; default_access?: "none" | "view" }) =>
      apiFetch<Folder>("/folders", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["folders"] }),
  })
}

export function useRenameFolder() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ folderId, name }: { folderId: string; name: string }) =>
      apiFetch<Folder>(`/folders/${folderId}`, { method: "PATCH", body: { name } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["folders"] }),
  })
}

export interface FolderDeleteBlocked {
  message: string
  per_deal: Record<string, number>
}

export function isFolderDeleteBlocked(err: unknown): err is ApiError & { detail: FolderDeleteBlocked } {
  return err instanceof ApiError && typeof err.detail === "object" && err.detail !== null && "per_deal" in err.detail
}

export function useDeleteFolder() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (folderId: string) => apiFetch<void>(`/folders/${folderId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["folders"] }),
  })
}
