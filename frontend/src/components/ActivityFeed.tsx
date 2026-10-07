import { avatarColor, formatDateTime, initials } from "@/lib/utils"
import type { AuditLogItem } from "@/api/types"

// DESIGN.md §6.11 wants a sentence: "Meera Shah uploaded 'SBI sanction
// letter.pdf' to Bank documents in Krishna Steel." Built from the action
// name plus whatever the detail blob carries, with a phrase per action
// only where the generic reading would be wrong or clumsy. Anything
// unlisted still reads sensibly ("document.renamed" -> "renamed the
// document"), so a new action never shows up blank.
const PHRASE: Record<string, string> = {
  "deal.created": "created this deal",
  "deal.stage_changed": "changed the stage",
  "document.uploaded": "uploaded",
  "document.renamed": "renamed",
  "document.archived": "moved to the Archive",
  "document.delete_requested": "requested deletion of",
  "document.restored": "restored",
  "document.purged": "permanently deleted",
  "task.created": "created the task",
  "task.assigned": "assigned the task",
  "task.reassigned": "reassigned the task",
  "task.reassignment_requested": "asked to reassign the task",
  "task.deleted": "deleted the task",
  "task.delete_requested": "asked to delete the task",
  "approval.approved": "approved a request",
  "approval.rejected": "rejected a request",
  "user.created": "added a user",
  "user.updated": "changed a user",
  "user.password_reset": "reset a password",
  "permission.changed": "changed folder access",
  "auth.login_succeeded": "signed in",
  "auth.login_failed": "failed to sign in",
}

function detailOf(item: AuditLogItem): Record<string, unknown> {
  return item.detail && typeof item.detail === "object" && !Array.isArray(item.detail)
    ? (item.detail as Record<string, unknown>)
    : {}
}

export function describeActivity(item: AuditLogItem): string {
  const d = detailOf(item)
  const [noun, verb] = [item.action.split(".")[0] ?? "", item.action.split(".")[1] ?? item.action]
  const phrase = PHRASE[item.action] ?? `${verb.replace(/_/g, " ")} the ${noun}`

  const parts: string[] = [phrase]

  if (typeof d.to === "string") parts.push(`to '${d.to}'`)
  else if (typeof d.title === "string") parts.push(`'${d.title}'`)
  else if (typeof d.name === "string") parts.push(`'${d.name}'`)

  if (item.action === "deal.stage_changed" && typeof d.to_stage === "string") {
    parts.push(`from ${d.from_stage} to ${d.to_stage}`)
  }
  if (typeof d.reason === "string" && d.reason) parts.push(`— ${d.reason}`)

  return parts.join(" ")
}

export function ActivityFeed({
  items,
  isLoading,
  showDeal = false,
  emptyTitle = "No activity yet",
  emptyBody = "Actions on this deal will be recorded here.",
}: {
  items: AuditLogItem[] | undefined
  isLoading: boolean
  showDeal?: boolean
  emptyTitle?: string
  emptyBody?: string
}) {
  if (isLoading) {
    return (
      <div className="p-4">
        <div className="h-3 w-1/3 animate-pulse rounded bg-surface-sunken" />
      </div>
    )
  }

  if (!items || items.length === 0) {
    return (
      <div className="px-4 py-10 text-center">
        <p className="text-body-strong text-text-primary">{emptyTitle}</p>
        <p className="text-table text-text-secondary">{emptyBody}</p>
      </div>
    )
  }

  return (
    <div>
      {items.map((item) => (
        <div
          key={item.id}
          className="flex min-h-9 items-center gap-3 border-b border-border px-4 py-1.5 last:border-b-0"
        >
          <span className="w-36 shrink-0 text-meta tabular-nums text-text-tertiary">
            {formatDateTime(item.created_at)}
          </span>
          <span
            className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[9px] font-semibold text-text-primary"
            style={{ backgroundColor: item.actor_id ? avatarColor(item.actor_id) : undefined }}
            aria-hidden
          >
            {item.actor_name ? initials(item.actor_name) : "·"}
          </span>
          <span className="text-table text-text-secondary">
            <span className="font-medium text-text-primary">{item.actor_name ?? "Someone"}</span>{" "}
            {describeActivity(item)}
            {showDeal && item.deal_name && (
              <span className="text-text-tertiary"> in {item.deal_name}</span>
            )}
          </span>
        </div>
      ))}
    </div>
  )
}
