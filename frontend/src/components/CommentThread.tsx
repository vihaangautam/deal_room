import { useState } from "react"
import { useComments, useCreateComment, useDeleteComment, useEditComment } from "@/api/comments"
import { useAuthStore } from "@/stores/auth"
import { Button } from "@/components/ui/button"
import { Avatar } from "@/components/ui/avatar"
import { UserName } from "@/components/UserName"
import { formatDateTime } from "@/lib/utils"
import type { Comment } from "@/api/types"

// PRD F8: the author may edit or delete within 15 minutes. The backend
// enforces the same window — this only decides whether to offer it.
const EDIT_WINDOW_MS = 15 * 60 * 1000

function Composer({
  placeholder,
  pending,
  submitLabel,
  autoFocus = false,
  onSubmit,
  onCancel,
}: {
  placeholder: string
  pending: boolean
  submitLabel: string
  autoFocus?: boolean
  onSubmit: (body: string) => void
  onCancel?: () => void
}) {
  const user = useAuthStore((s) => s.user)
  const [body, setBody] = useState("")

  function submit() {
    const trimmed = body.trim()
    if (!trimmed) return
    onSubmit(trimmed)
    setBody("")
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        <Avatar name={user?.display_name ?? ""} />
        <textarea
          autoFocus={autoFocus}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={(e) => {
            // DESIGN.md §5.11: Ctrl/Cmd+Enter submits.
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit()
          }}
          placeholder={placeholder}
          className="h-16 flex-1 rounded-md border border-border bg-surface-sunken p-2 text-body focus:outline-none focus:ring-2 focus:ring-brand-600"
        />
      </div>
      <div className="flex justify-end gap-2">
        {onCancel && (
          <Button size="sm" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button size="sm" onClick={submit} loading={pending}>
          {submitLabel}
        </Button>
      </div>
    </div>
  )
}

function CommentBody({
  comment,
  canAct,
  onEdit,
  onDelete,
  onReply,
}: {
  comment: Comment
  canAct: boolean
  onEdit: (body: string) => void
  onDelete: () => void
  onReply?: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(comment.body)

  return (
    <div className="flex-1">
      <div className="flex items-center gap-2">
        <span className="text-body-strong text-text-primary">
          <UserName name={comment.author_name} id={comment.author_id} />
        </span>
        <span className="text-meta text-text-tertiary">{formatDateTime(comment.created_at)}</span>
        {comment.edited && <span className="text-meta text-text-tertiary">Edited</span>}
      </div>

      {editing ? (
        <div className="mt-1 flex flex-col gap-1">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="h-16 rounded-md border border-border bg-surface-sunken p-2 text-body"
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => {
                onEdit(draft)
                setEditing(false)
              }}
            >
              Save
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <p className={comment.deleted ? "italic text-text-tertiary" : "text-body text-text-primary"}>
          {comment.body}
        </p>
      )}

      {!comment.deleted && !editing && (
        <div className="mt-1 flex gap-2 text-meta text-text-tertiary">
          {onReply && (
            <button type="button" className="hover:text-text-secondary" onClick={onReply}>
              Reply
            </button>
          )}
          {canAct && (
            <>
              <button
                type="button"
                className="hover:text-text-secondary"
                onClick={() => {
                  setDraft(comment.body)
                  setEditing(true)
                }}
              >
                Edit
              </button>
              <button type="button" className="hover:text-text-secondary" onClick={onDelete}>
                Delete
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export function CommentThread({
  dealId,
  taskId,
  readOnly,
}: {
  dealId: string
  taskId?: string
  readOnly: boolean
}) {
  const user = useAuthStore((s) => s.user)
  const { data: comments } = useComments(dealId, taskId)
  const createComment = useCreateComment(dealId, taskId)
  const editComment = useEditComment(dealId, taskId)
  const deleteComment = useDeleteComment(dealId, taskId)
  const [replyingTo, setReplyingTo] = useState<string | null>(null)

  const all = comments ?? []
  const topLevel = all.filter((c) => !c.parent_id)
  const repliesFor = (parentId: string) => all.filter((c) => c.parent_id === parentId)

  function canAct(comment: Comment): boolean {
    return (
      !readOnly &&
      comment.author_id === user?.id &&
      Date.now() - new Date(comment.created_at).getTime() < EDIT_WINDOW_MS
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {!readOnly && (
        <Composer
          placeholder="Add a comment"
          submitLabel="Comment"
          pending={createComment.isPending}
          onSubmit={(body) => createComment.mutate({ body })}
        />
      )}

      {topLevel.length === 0 && (
        <p className="text-table text-text-tertiary">No comments yet.</p>
      )}

      {topLevel.map((comment) => (
        <div key={comment.id} className="flex flex-col gap-2">
          <div className="flex gap-2">
            <Avatar name={comment.author_name} />
            <CommentBody
              comment={comment}
              canAct={canAct(comment)}
              onEdit={(body) => editComment.mutate({ commentId: comment.id, body })}
              onDelete={() => deleteComment.mutate(comment.id)}
              {...(readOnly ? {} : { onReply: () => setReplyingTo(comment.id) })}
            />
          </div>

          {/* PRD F8 allows one level only, and the API rejects a reply to
              a reply — so replies carry no Reply control of their own. */}
          {repliesFor(comment.id).map((reply) => (
            <div key={reply.id} className="ml-8 flex gap-2">
              <Avatar name={reply.author_name} />
              <CommentBody
                comment={reply}
                canAct={canAct(reply)}
                onEdit={(body) => editComment.mutate({ commentId: reply.id, body })}
                onDelete={() => deleteComment.mutate(reply.id)}
              />
            </div>
          ))}

          {replyingTo === comment.id && (
            <div className="ml-8">
              <Composer
                autoFocus
                placeholder={`Reply to ${comment.author_name}`}
                submitLabel="Reply"
                pending={createComment.isPending}
                onCancel={() => setReplyingTo(null)}
                onSubmit={(body) => {
                  createComment.mutate({ body, parent_id: comment.id })
                  setReplyingTo(null)
                }}
              />
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
