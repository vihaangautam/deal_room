import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "./client"
import type { Comment } from "./types"

export function useTaskComments(dealId: string | undefined, taskId: string | undefined) {
  return useQuery({
    queryKey: ["comments", "task", taskId],
    queryFn: () => apiFetch<Comment[]>(`/deals/${dealId}/tasks/${taskId}/comments`),
    enabled: !!dealId && !!taskId,
  })
}

export function useCreateTaskComment(dealId: string, taskId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { body: string; parent_id?: string }) =>
      apiFetch<Comment>(`/deals/${dealId}/tasks/${taskId}/comments`, { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["comments", "task", taskId] }),
  })
}

export function useEditComment(taskId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ commentId, body }: { commentId: string; body: string }) =>
      apiFetch<Comment>(`/comments/${commentId}`, { method: "PATCH", body: { body } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["comments", "task", taskId] }),
  })
}

export function useDeleteComment(taskId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (commentId: string) => apiFetch<void>(`/comments/${commentId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["comments", "task", taskId] }),
  })
}
