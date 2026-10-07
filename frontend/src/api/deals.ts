import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "./client"
import { DEAL_STAGE_LABEL } from "@/components/StatusPill"
import { toast } from "@/components/ui/toast"
import type {
  AuditLogItem,
  DealDetail,
  DealListItem,
  DealStage,
  DealStageHistoryItem,
} from "./types"

export function useDeals(params?: { stage?: DealStage; search?: string }) {
  const query = new URLSearchParams()
  if (params?.stage) query.set("stage", params.stage)
  if (params?.search) query.set("search", params.search)
  const qs = query.toString()

  return useQuery({
    queryKey: ["deals", params?.stage, params?.search],
    queryFn: () => apiFetch<DealListItem[]>(`/deals${qs ? `?${qs}` : ""}`),
  })
}

export function useDeal(dealId: string | undefined) {
  return useQuery({
    queryKey: ["deals", dealId],
    queryFn: () => apiFetch<DealDetail>(`/deals/${dealId}`),
    enabled: !!dealId,
  })
}

export function useDealStageHistory(dealId: string | undefined) {
  return useQuery({
    queryKey: ["deals", dealId, "stage-history"],
    queryFn: () => apiFetch<DealStageHistoryItem[]>(`/deals/${dealId}/stage-history`),
    enabled: !!dealId,
  })
}

export function useCreateDeal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; short_code: string; borrower: string; summary: string }) =>
      apiFetch<DealDetail>("/deals", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["deals"] }),
  })
}

// Admin-only on the server (PRD §7), so callers pass undefined for a
// member and the query simply doesn't run.
export function useDealActivity(dealId: string | undefined) {
  return useQuery({
    queryKey: ["deals", dealId, "activity"],
    queryFn: () => apiFetch<AuditLogItem[]>(`/deals/${dealId}/activity`),
    enabled: !!dealId,
  })
}

export function useChangeStage(dealId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { to_stage: DealStage; reason: string }) =>
      apiFetch<DealDetail>(`/deals/${dealId}/stage`, { method: "POST", body }),
    onSuccess: (deal) => {
      qc.invalidateQueries({ queryKey: ["deals"] })
      qc.invalidateQueries({ queryKey: ["deals", dealId, "stage-history"] })
      toast(`Deal moved to ${DEAL_STAGE_LABEL[deal.stage] ?? deal.stage}.`)
    },
  })
}
