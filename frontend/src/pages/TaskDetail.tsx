import { useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { Lock, Paperclip } from "lucide-react"
import {
  useAssignTask,
  useChangeTaskStatus,
  useLinkAttachment,
  useRequestDeleteTask,
  useSubmitTask,
  useTask,
  useUpdateTask,
} from "@/api/tasks"
import { CommentThread } from "@/components/CommentThread"
import { useDeal } from "@/api/deals"
import { useDocuments } from "@/api/documents"
import { useUsers } from "@/api/users"
import { useAuthStore } from "@/stores/auth"
import { TaskStatusPill, NeedsAttentionPill, DocumentStatusPill } from "@/components/StatusPill"
import { Button } from "@/components/ui/button"
import { Menu, RowMenuItem } from "@/components/ui/dropdown-menu"
import { formatDate, formatDateTime, initials } from "@/lib/utils"
import type { TaskAttachmentItem } from "@/api/types"

function AttachmentRow({ attachment }: { attachment: TaskAttachmentItem }) {
  if (attachment.restricted) {
    return (
      <div className="flex h-9 items-center gap-2 border-b border-border px-1 last:border-b-0">
        <Lock className="h-4 w-4 text-text-tertiary" aria-hidden />
        <span className="text-table text-text-tertiary">Restricted document</span>
      </div>
    )
  }
  return (
    <div className="flex h-9 items-center gap-2 border-b border-border px-1 last:border-b-0">
      <Paperclip className="h-4 w-4 text-text-tertiary" aria-hidden />
      <span className="text-table text-text-primary">{attachment.display_name}</span>
      <span className="text-meta text-text-tertiary">{attachment.folder_name}</span>
      {attachment.status && <DocumentStatusPill status={attachment.status} />}
    </div>
  )
}

export function TaskDetail() {
  const { dealId, taskId } = useParams<{ dealId: string; taskId: string }>()
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const { data: task } = useTask(dealId, taskId)
  const { data: deal } = useDeal(dealId)
  const { data: users } = useUsers()
  const { data: documents } = useDocuments(dealId)
  const updateTask = useUpdateTask(dealId ?? "", taskId ?? "")
  const assignTask = useAssignTask(dealId ?? "", taskId ?? "")
  const changeStatus = useChangeTaskStatus(dealId ?? "", taskId ?? "")
  const submitTask = useSubmitTask(dealId ?? "", taskId ?? "")
  const requestDelete = useRequestDeleteTask(dealId ?? "", taskId ?? "")
  const linkAttachment = useLinkAttachment(dealId ?? "", taskId ?? "")

  const [editingDescription, setEditingDescription] = useState(false)
  const [description, setDescription] = useState("")

  if (!dealId || !taskId || !task) return null

  // PRD F3: "task edit" is among the things a closed deal disables. The
  // Tasks tab is hidden on such a deal, but this page is still reachable
  // by a bookmarked URL and its reads still resolve, so without this
  // every control rendered live and then failed with a 403 on click.
  const dealClosed = deal?.stage === "successful" || deal?.stage === "dropped"
  const canEditDescription =
    !dealClosed &&
    (user?.role === "admin" || task.assigned_by_id === user?.id || task.assignee_id === null)
  const canActOnTask =
    !dealClosed &&
    (user?.role === "admin" || task.assignee_id === user?.id || task.assigned_by_id === user?.id)
  // PRD F8: assigning an unassigned task and an approver's reassignment
  // both take effect immediately; only a member moving an already-assigned
  // task raises a request. One label covered all three cases.
  const assignLabel =
    task.assignee_id === null
      ? "Assign"
      : user?.role === "admin" || user?.can_approve
        ? "Reassign"
        : "Request reassignment"
  const hasPendingAttachments = task.attachments.some(
    (a) => a.status === "pending" || a.status === "uploading",
  )
  const submitLabel = hasPendingAttachments ? "Submit for approval" : "Mark as done"

  const linkableDocuments = (documents ?? []).filter(
    (d) => d.status === "active" && !task.attachments.some((a) => a.document_id === d.id),
  )

  return (
    <div className="mx-auto flex max-w-content gap-6 px-6 py-6">
      <div className="min-w-[560px] flex-1">
        <p className="mb-1 text-meta text-text-tertiary">{task.key}</p>
        <h1 className="mb-4 text-title-task text-text-primary">{task.title}</h1>

        {canActOnTask && (
          <div className="mb-6 flex items-center gap-2">
            <Menu
              trigger={
                <Button variant="secondary" size="sm">
                  <Paperclip className="h-3.5 w-3.5" />
                  Attach
                </Button>
              }
            >
              {linkableDocuments.length === 0 && (
                <p className="px-3 py-2 text-meta text-text-tertiary">No documents to link.</p>
              )}
              {linkableDocuments.map((doc) => (
                <RowMenuItem key={doc.id} onSelect={() => linkAttachment.mutate(doc.id)}>
                  {doc.display_name}
                </RowMenuItem>
              ))}
            </Menu>
          </div>
        )}

        <section className="mb-6">
          <h2 className="mb-1 text-label text-text-tertiary">Description</h2>
          {editingDescription ? (
            <div className="flex flex-col gap-2">
              <textarea
                autoFocus
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="h-24 rounded-md border border-border bg-surface-sunken p-2 text-body focus:outline-none focus:ring-2 focus:ring-brand-600"
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={() => {
                    updateTask.mutate({ description })
                    setEditingDescription(false)
                  }}
                >
                  Save
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setEditingDescription(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              disabled={!canEditDescription}
              onClick={() => {
                setDescription(task.description ?? "")
                setEditingDescription(true)
              }}
              title={!canEditDescription ? "Only Samir or the person who assigned this task can edit it." : undefined}
              className="w-full text-left text-body text-text-primary disabled:cursor-not-allowed"
            >
              {task.description || <span className="text-text-tertiary">No description.</span>}
            </button>
          )}
        </section>

        <section className="mb-6">
          <h2 className="mb-1 text-label text-text-tertiary">Attachments</h2>
          {task.attachments.length === 0 ? (
            <p className="text-table text-text-tertiary">No attachments yet.</p>
          ) : (
            <div className="rounded-md border border-border">
              {task.attachments.map((a) => (
                <AttachmentRow key={a.document_id} attachment={a} />
              ))}
            </div>
          )}
        </section>

        <section className="mb-6">
          <h2 className="mb-2 text-label text-text-tertiary">Activity</h2>
          <CommentThread dealId={dealId} taskId={taskId} readOnly={dealClosed} />
        </section>

        <div className="flex justify-end gap-2 border-t border-border pt-4">
          {!dealClosed && (
            <Menu trigger={<Button variant="secondary">{assignLabel}</Button>}>
              {(users ?? [])
                .filter((u) => u.id !== task.assignee_id)
                .map((u) => (
                  <RowMenuItem key={u.id} onSelect={() => assignTask.mutate(u.id)}>
                    {u.display_name}
                  </RowMenuItem>
                ))}
            </Menu>
          )}
          {canActOnTask && task.status !== "done" && (
            <Button onClick={() => submitTask.mutate()} loading={submitTask.isPending}>
              {submitLabel}
            </Button>
          )}
        </div>
      </div>

      <aside className="w-80 shrink-0 rounded-md border border-border p-4">
        <h2 className="mb-2 text-label text-text-tertiary">Status</h2>
        <select
          value={task.status}
          disabled={!canActOnTask}
          onChange={(e) => {
            const next = e.target.value
            if (next === "not_started" || next === "in_progress") {
              changeStatus.mutate(next)
            }
          }}
          className="mb-4 h-9 w-full rounded-md border border-border bg-surface-sunken px-2 text-body disabled:opacity-60"
        >
          <option value="not_started">Not started</option>
          <option value="in_progress">In progress</option>
          <option value="submitted" disabled>
            Awaiting approval
          </option>
          <option value="done" disabled>
            Done
          </option>
        </select>
        <div className="mb-3">
          <TaskStatusPill status={task.status} />
          {task.needs_attention && (
            <span className="ml-1.5">
              <NeedsAttentionPill />
            </span>
          )}
        </div>

        <h2 className="mb-2 text-label text-text-tertiary">Details</h2>
        <dl className="flex flex-col gap-2 text-table">
          <Detail label="Assignee">
            {task.assignee_name ?? "Unassigned"}
            {!dealClosed && !task.assignee_id && user && (
              <button
                type="button"
                className="ml-2 text-meta text-brand-700 hover:underline"
                onClick={() => assignTask.mutate(user.id)}
              >
                Assign to me
              </button>
            )}
          </Detail>
          {task.pending_reassignment_to && (
            <p className="rounded bg-warning-50 px-2 py-1 text-meta text-text-warning">
              Reassignment to {task.pending_reassignment_to} waiting for approval
            </p>
          )}
          <Detail label="Reporter">{task.reporter_name}</Detail>
          <Detail label="Assigned by">{task.assigned_by_name ?? "—"}</Detail>
          <Detail label="Start date">{task.start_date ? formatDate(task.start_date) : "—"}</Detail>
          <Detail label="Due date">{task.due_date ? formatDate(task.due_date) : "—"}</Detail>
          <Detail label="Created">{formatDate(task.created_at)}</Detail>
          <Detail label="Updated">{formatDateTime(task.updated_at)}</Detail>
        </dl>

        {canActOnTask && (
          <Button
            variant="ghost"
            size="sm"
            className="mt-4 text-text-danger"
            onClick={async () => {
              await requestDelete.mutateAsync()
              navigate(`/deals/${dealId}/tasks`)
            }}
          >
            Delete task
          </Button>
        )}
      </aside>
    </div>
  )
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex">
      <dt className="w-24 shrink-0 text-text-tertiary">{label}</dt>
      <dd className="text-text-primary">{children}</dd>
    </div>
  )
}
