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
    mutationFn: (body: {
      ids: string[]
      action: "approve" | "reject"
      /** One reason for the whole batch. */
      note?: string
      /** A reply typed against one row, which wins over `note` for it. */
      notes?: Record<string, string>
    }) => apiFetch<BulkActionResult>("/approvals/bulk", { method: "POST", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["approvals"] })
      qc.invalidateQueries({ queryKey: ["deals"] })
      qc.invalidateQueries({ queryKey: ["tasks"] })
      // A reply is posted to the thread it belongs to, so the comment
      // counts in the deal tab bar are stale the moment this returns.
      qc.invalidateQueries({ queryKey: ["comments"] })
      // document_upload and document_delete decisions are exactly what
      // moves a document between pending/active/archived.
      qc.invalidateQueries({ queryKey: ["documents"] })
    },
  })
}
