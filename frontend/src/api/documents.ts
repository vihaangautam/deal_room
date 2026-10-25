import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "./client"
import type { DocumentItem } from "./types"

export function useDocuments(dealId: string | undefined) {
  return useQuery({
    queryKey: ["documents", dealId],
    queryFn: () => apiFetch<DocumentItem[]>(`/deals/${dealId}/documents`),
    enabled: !!dealId,
  })
}

export function useRenameDocument(dealId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ docId, baseName }: { docId: string; baseName: string }) =>
      apiFetch<DocumentItem>(`/deals/${dealId}/documents/${docId}`, {
        method: "PATCH",
        body: { base_name: baseName },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents", dealId] }),
  })
}

export function useMoveDocument(dealId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ docId, folderId }: { docId: string; folderId: string }) =>
      apiFetch<DocumentItem>(`/deals/${dealId}/documents/${docId}/move`, {
        method: "PATCH",
        body: { folder_id: folderId },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents", dealId] })
      qc.invalidateQueries({ queryKey: ["folders"] })
      qc.invalidateQueries({ queryKey: ["deal-activity", dealId] })
      qc.invalidateQueries({ queryKey: ["audit-log"] })
    },
  })
}


export function useRequestDeleteDocument(dealId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ docId, reason }: { docId: string; reason?: string }) =>
      apiFetch<{ status: string }>(`/deals/${dealId}/documents/${docId}`, {
        method: "DELETE",
        body: { reason },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents", dealId] })
      qc.invalidateQueries({ queryKey: ["approvals"] })
    },
  })
}

export function documentDownloadUrl(dealId: string, docId: string): string {
  const base = (import.meta.env.VITE_API_URL as string | undefined) ?? ""
  return `${base}/deals/${dealId}/documents/${docId}/download`
}

/**
 * Opens in the browser's own viewer instead of saving to disk. The server
 * honours it for PDFs only — a .docx asked for inline downloads anyway.
 * Not a preview feature: there is no viewer in this app, it just stops
 * forcing a download of something Chrome already renders.
 */
export function documentViewUrl(dealId: string, docId: string): string {
  return `${documentDownloadUrl(dealId, docId)}?inline=true`
}

/** PDFs open in a tab; everything else can only be downloaded. */
export function canOpenInBrowser(mimeType: string | null | undefined): boolean {
  return mimeType === "application/pdf"
}
