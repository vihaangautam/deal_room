import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "./client"
import type { ApprovalItem, ApprovalType, BulkActionResult } from "./types"

// DESIGN.md §4.2: the sidebar badge "refreshes every 60 seconds and
// after any mutation" (PRD F7).
export function useApprovals(filters?: { dealId?: string; requestedBy?: string; type?: ApprovalType }) {
  const query = new URLSearchParams()
  if (filters?.dealId) query.set("deal_id", filters.dealId)
  if (filters?.requestedBy) query.set("requested_by", filters.requestedBy)
  if (filters?.type) query.set("type", filters.type)
  const qs = query.toString()

  return useQuery({
    queryKey: ["approvals", filters?.dealId, filters?.requestedBy, filters?.type],
    queryFn: () => apiFetch<ApprovalItem[]>(`/approvals${qs ? `?${qs}` : ""}`),
    refetchInterval: 60_000,
  })
}

export function useBulkApprovalAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { ids: string[]; action: "approve" | "reject"; note?: string }) =>
      apiFetch<BulkActionResult>("/approvals/bulk", { method: "POST", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["approvals"] })
      qc.invalidateQueries({ queryKey: ["deals"] })
      qc.invalidateQueries({ queryKey: ["tasks"] })
      // document_upload and document_delete decisions are exactly what
      // moves a document between pending/active/archived.
      qc.invalidateQueries({ queryKey: ["documents"] })
    },
  })
}
