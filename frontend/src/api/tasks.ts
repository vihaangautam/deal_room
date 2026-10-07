import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "./client"
import type { TaskDetail, TaskListItem, TaskPriority } from "./types"

export function useTasks(dealId: string | undefined) {
  return useQuery({
    queryKey: ["tasks", "deal", dealId],
    queryFn: () => apiFetch<TaskListItem[]>(`/deals/${dealId}/tasks`),
    enabled: !!dealId,
  })
}

export function useMyTasks() {
  return useQuery({
    queryKey: ["tasks", "mine"],
    queryFn: () => apiFetch<TaskListItem[]>("/tasks"),
  })
}

export function useTask(dealId: string | undefined, taskId: string | undefined) {
  return useQuery({
    queryKey: ["tasks", dealId, taskId],
    queryFn: () => apiFetch<TaskDetail>(`/deals/${dealId}/tasks/${taskId}`),
    enabled: !!dealId && !!taskId,
  })
}

function invalidateTask(qc: ReturnType<typeof useQueryClient>, dealId: string, taskId?: string) {
  qc.invalidateQueries({ queryKey: ["tasks", "deal", dealId] })
  qc.invalidateQueries({ queryKey: ["tasks", "mine"] })
  if (taskId) qc.invalidateQueries({ queryKey: ["tasks", dealId, taskId] })
}

export function useCreateTask(dealId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      title: string
      description?: string
      assignee_id?: string
      priority?: TaskPriority
      start_date?: string
      due_date?: string
    }) => apiFetch<TaskDetail>(`/deals/${dealId}/tasks`, { method: "POST", body }),
    onSuccess: () => invalidateTask(qc, dealId),
  })
}

export function useUpdateTask(dealId: string, taskId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      title?: string
      description?: string
      priority?: TaskPriority
      start_date?: string | null
      due_date?: string | null
    }) => apiFetch<TaskDetail>(`/deals/${dealId}/tasks/${taskId}`, { method: "PATCH", body }),
    onSuccess: () => invalidateTask(qc, dealId, taskId),
  })
}

export function useAssignTask(dealId: string, taskId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (assigneeId: string) =>
      apiFetch<TaskDetail>(`/deals/${dealId}/tasks/${taskId}/assign`, {
        method: "POST",
        body: { assignee_id: assigneeId },
      }),
    onSuccess: () => {
      invalidateTask(qc, dealId, taskId)
      qc.invalidateQueries({ queryKey: ["approvals"] })
    },
  })
}

export function useChangeTaskStatus(dealId: string, taskId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (status: "not_started" | "in_progress") =>
      apiFetch<TaskDetail>(`/deals/${dealId}/tasks/${taskId}/status`, {
        method: "POST",
        body: { status },
      }),
    onSuccess: () => invalidateTask(qc, dealId, taskId),
  })
}

export function useSubmitTask(dealId: string, taskId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      apiFetch<TaskDetail>(`/deals/${dealId}/tasks/${taskId}/submit`, { method: "POST" }),
    onSuccess: () => {
      invalidateTask(qc, dealId, taskId)
      qc.invalidateQueries({ queryKey: ["approvals"] })
    },
  })
}

export function useRequestDeleteTask(dealId: string, taskId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      apiFetch<{ status: string }>(`/deals/${dealId}/tasks/${taskId}`, { method: "DELETE" }),
    onSuccess: () => {
      invalidateTask(qc, dealId, taskId)
      qc.invalidateQueries({ queryKey: ["approvals"] })
    },
  })
}

export function useLinkAttachment(dealId: string, taskId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (documentId: string) =>
      apiFetch<TaskDetail>(`/deals/${dealId}/tasks/${taskId}/attachments/link`, {
        method: "POST",
        body: { document_id: documentId },
      }),
    onSuccess: () => invalidateTask(qc, dealId, taskId),
  })
}
