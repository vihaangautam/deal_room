import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "./client"
import type { Comment } from "./types"

// A deal has its own comment thread and so does each task — same shape,
// same rules, two paths. taskId picks which; omitting it means the deal's
// own thread, which the Activity tab uses.
function path(dealId: string, taskId: string | undefined): string {
  return taskId ? `/deals/${dealId}/tasks/${taskId}/comments` : `/deals/${dealId}/comments`
}

function key(dealId: string | undefined, taskId: string | undefined) {
  return ["comments", dealId, taskId ?? null]
}

export function useComments(dealId: string | undefined, taskId?: string) {
  return useQuery({
    queryKey: key(dealId, taskId),
    queryFn: () => apiFetch<Comment[]>(path(dealId!, taskId)),
    enabled: !!dealId && (taskId === undefined || !!taskId),
  })
}

export function useCreateComment(dealId: string, taskId?: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { body: string; parent_id?: string }) =>
      apiFetch<Comment>(path(dealId, taskId), { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: key(dealId, taskId) }),
  })
}

// Editing and deleting go to /comments/{id} whichever thread the comment
// is in; the ids are only here to invalidate the right list.
export function useEditComment(dealId: string, taskId?: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ commentId, body }: { commentId: string; body: string }) =>
      apiFetch<Comment>(`/comments/${commentId}`, { method: "PATCH", body: { body } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: key(dealId, taskId) }),
  })
}

export function useDeleteComment(dealId: string, taskId?: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (commentId: string) => apiFetch<void>(`/comments/${commentId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: key(dealId, taskId) }),
  })
}
