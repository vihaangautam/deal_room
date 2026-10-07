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
  const base = import.meta.env.VITE_API_URL as string
  return `${base}/deals/${dealId}/documents/${docId}/download`
}
