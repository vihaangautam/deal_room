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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["folders"] })
      // PRD F4: a new folder's default access applies to current members
      // at once, so each viewer's own access map changed too.
      qc.invalidateQueries({ queryKey: ["my-permissions"] })
    },
  })
}

export function useReorderFolders() {
  const qc = useQueryClient()
  return useMutation({
    // One request for the whole order: a reorder applied one folder at a
    // time can half-fail and scramble the list in every deal.
    mutationFn: (folderIds: string[]) =>
      apiFetch<Folder[]>("/folders/order", { method: "POST", body: { folder_ids: folderIds } }),
    onSuccess: (folders) => {
      qc.setQueryData(["folders"], folders)
      qc.invalidateQueries({ queryKey: ["folders"] })
    },
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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["folders"] })
      // The deleted folder's permission rows went with it.
      qc.invalidateQueries({ queryKey: ["my-permissions"] })
    },
  })
}
