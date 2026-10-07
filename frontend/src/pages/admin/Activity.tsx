import { useAuditLog } from "@/api/admin"
import { formatDateTime, initials } from "@/lib/utils"

// DESIGN.md §6.11: "{actor} {verb-ish summary of action} in {deal}." —
// built here from the structured action/detail fields rather than a
// hand-written sentence per action type, which would need one entry per
// AuditLog.action value and go stale the moment a new one is added.
function describe(action: string, detail: unknown): string {
  const d = (detail && typeof detail === "object" ? (detail as Record<string, unknown>) : {}) ?? {}
  const verb = action.split(".")[1]?.replace(/_/g, " ") ?? action
  const noun = action.split(".")[0] ?? "item"
  const name = typeof d.name === "string" ? ` '${d.name}'` : ""
  return `${noun}${name} ${verb}`
}

export function Activity() {
  const { data: logs, isLoading } = useAuditLog()

  return (
    <div className="px-6 py-6">
      <h1 className="mb-4 text-title-page text-text-primary">Activity</h1>

      <div className="rounded-md border border-border">
        {isLoading && (
          <div className="p-4">
            <div className="h-3 w-1/3 animate-pulse rounded bg-surface-sunken" />
          </div>
        )}
        {!isLoading && (logs?.length ?? 0) === 0 && (
          <div className="px-4 py-10 text-center">
            <p className="text-body-strong text-text-primary">No activity yet</p>
            <p className="text-table text-text-secondary">Actions on this deal will be recorded here.</p>
          </div>
        )}
        {logs?.map((log) => (
          <div key={log.id} className="flex h-9 items-center gap-3 border-b border-border px-4 last:border-b-0">
            <span className="w-32 shrink-0 text-meta text-text-tertiary">
              {formatDateTime(log.created_at)}
            </span>
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-pill-neutral-bg text-[9px] font-semibold">
              {log.actor_id ? initials(log.entity_type) : "·"}
            </span>
            <span className="truncate text-table text-text-primary">
              {describe(log.action, log.detail)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
