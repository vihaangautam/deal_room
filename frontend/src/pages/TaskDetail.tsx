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
import { useCreateTaskComment, useDeleteComment, useEditComment, useTaskComments } from "@/api/comments"
import { useDocuments } from "@/api/documents"
import { useUsers } from "@/api/users"
import { useAuthStore } from "@/stores/auth"
import { TaskStatusPill, NeedsAttentionPill, DocumentStatusPill } from "@/components/StatusPill"
import { Button } from "@/components/ui/button"
import { formatDate, formatDateTime, initials } from "@/lib/utils"
import type { TaskAttachmentItem } from "@/api/types"

const EDIT_WINDOW_MS = 15 * 60 * 1000

function AssigneePicker({
  users,
  excludeUserId,
  onPick,
  trigger,
}: {
  users: { id: string; display_name: string }[]
  excludeUserId: string | null
  onPick: (userId: string) => void
  trigger: React.ReactNode
}) {
  const [open, setOpen] = useState(false)
  const choices = users.filter((u) => u.id !== excludeUserId)
  return (
    <div className="relative inline-block">
      <button type="button" onClick={() => setOpen((v) => !v)}>
        {trigger}
      </button>
      {open && (
        <div className="absolute left-0 top-6 z-10 max-h-48 w-48 overflow-y-auto rounded-md border border-border bg-surface py-1 shadow-[0_4px_12px_rgba(16,24,16,.08),0_0_0_1px_#E3E6E3]">
          {choices.map((u) => (
            <button
              key={u.id}
              type="button"
              onClick={() => {
                onPick(u.id)
                setOpen(false)
              }}
              className="block w-full px-3 py-1.5 text-left text-body text-text-primary hover:bg-surface-hover"
            >
              {u.display_name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

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

function CommentThread({ dealId, taskId }: { dealId: string; taskId: string }) {
  const user = useAuthStore((s) => s.user)
  const { data: comments } = useTaskComments(dealId, taskId)
  const createComment = useCreateTaskComment(dealId, taskId)
  const editComment = useEditComment(taskId)
  const deleteComment = useDeleteComment(taskId)
  const [body, setBody] = useState("")
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editBody, setEditBody] = useState("")

  function submit() {
    if (body.trim()) {
      createComment.mutate({ body: body.trim() })
      setBody("")
    }
  }

  const topLevel = (comments ?? []).filter((c) => !c.parent_id)
  const repliesFor = (parentId: string) => (comments ?? []).filter((c) => c.parent_id === parentId)

  function canEdit(authorId: string, createdAt: string): boolean {
    return authorId === user?.id && Date.now() - new Date(createdAt).getTime() < EDIT_WINDOW_MS
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-2">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-pill-neutral-bg text-[11px] font-semibold">
          {user ? initials(user.display_name) : ""}
        </span>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit()
          }}
          placeholder="Add a comment"
          className="h-16 flex-1 rounded-md border border-border bg-surface-sunken p-2 text-body focus:outline-none focus:ring-2 focus:ring-brand-600"
        />
      </div>
      <Button size="sm" className="self-end" onClick={submit} loading={createComment.isPending}>
        Comment
      </Button>

      {topLevel.map((c) => (
        <div key={c.id} className="flex flex-col gap-2">
          <div className="flex gap-2">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-pill-neutral-bg text-[11px] font-semibold">
              {initials(c.author_name)}
            </span>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-body-strong text-text-primary">{c.author_name}</span>
                <span className="text-meta text-text-tertiary">{formatDateTime(c.created_at)}</span>
              </div>
              {editingId === c.id ? (
                <div className="mt-1 flex flex-col gap-1">
                  <textarea
                    value={editBody}
                    onChange={(e) => setEditBody(e.target.value)}
                    className="h-16 rounded-md border border-border bg-surface-sunken p-2 text-body"
                  />
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={() => {
                        editComment.mutate({ commentId: c.id, body: editBody })
                        setEditingId(null)
                      }}
                    >
                      Save
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <p className={c.deleted ? "italic text-text-tertiary" : "text-body text-text-primary"}>
                  {c.body}
                </p>
              )}
              {!c.deleted && canEdit(c.author_id, c.created_at) && editingId !== c.id && (
                <div className="mt-1 flex gap-2 text-meta text-text-tertiary">
                  <button
                    type="button"
                    className="hover:text-text-secondary"
                    onClick={() => {
                      setEditingId(c.id)
                      setEditBody(c.body)
                    }}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="hover:text-text-secondary"
                    onClick={() => deleteComment.mutate(c.id)}
                  >
                    Delete
                  </button>
                </div>
              )}
            </div>
          </div>

          {repliesFor(c.id).map((reply) => (
            <div key={reply.id} className="ml-8 flex gap-2">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-pill-neutral-bg text-[11px] font-semibold">
                {initials(reply.author_name)}
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-body-strong text-text-primary">{reply.author_name}</span>
                  <span className="text-meta text-text-tertiary">{formatDateTime(reply.created_at)}</span>
                </div>
                <p className={reply.deleted ? "italic text-text-tertiary" : "text-body text-text-primary"}>
                  {reply.body}
                </p>
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

export function TaskDetail() {
  const { dealId, taskId } = useParams<{ dealId: string; taskId: string }>()
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const { data: task } = useTask(dealId, taskId)
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
  const [showLinkPicker, setShowLinkPicker] = useState(false)

  if (!dealId || !taskId || !task) return null

  const canEditDescription =
    user?.role === "admin" || task.assigned_by_id === user?.id || task.assignee_id === null
  const canActOnTask =
    user?.role === "admin" || task.assignee_id === user?.id || task.assigned_by_id === user?.id
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

        <div className="mb-6 flex items-center gap-2">
          <div className="relative">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowLinkPicker((v) => !v)}
            >
              <Paperclip className="h-3.5 w-3.5" />
              Attach
            </Button>
            {showLinkPicker && (
              <div className="absolute left-0 top-9 z-10 max-h-60 w-72 overflow-y-auto rounded-md border border-border bg-surface py-1 shadow-[0_4px_12px_rgba(16,24,16,.08),0_0_0_1px_#E3E6E3]">
                {linkableDocuments.length === 0 && (
                  <p className="px-3 py-2 text-meta text-text-tertiary">No documents to link.</p>
                )}
                {linkableDocuments.map((doc) => (
                  <button
                    key={doc.id}
                    type="button"
                    onClick={() => {
                      linkAttachment.mutate(doc.id)
                      setShowLinkPicker(false)
                    }}
                    className="block w-full px-3 py-1.5 text-left text-body text-text-primary hover:bg-surface-hover"
                  >
                    {doc.display_name}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

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
          <CommentThread dealId={dealId} taskId={taskId} />
        </section>

        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <AssigneePicker
            users={users ?? []}
            excludeUserId={task.assignee_id}
            onPick={(targetId) => assignTask.mutate(targetId)}
            trigger={
              <span className="inline-flex h-9 items-center rounded-md border border-border-strong bg-surface px-4 text-body-strong text-text-primary hover:bg-surface-sunken">
                Request reassignment
              </span>
            }
          />
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
            {!task.assignee_id && user && (
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
