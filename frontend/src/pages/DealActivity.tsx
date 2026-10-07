import { useState } from "react"
import { useParams } from "react-router-dom"
import { useDeal, useDealActivity } from "@/api/deals"
import { useAuthStore } from "@/stores/auth"
import { ActivityFeed } from "@/components/ActivityFeed"
import { CommentThread } from "@/components/CommentThread"
import { DealHeader } from "@/components/DealHeader"
import { cn } from "@/lib/utils"

// DESIGN.md §5.11 gives the Activity section underline tabs
// "All · Comments · History". History is the audit log, which PRD §7's
// permission matrix reserves for admin — so a member sees Comments alone
// and the sub-tabs collapse rather than offering an empty History.
type Pane = "all" | "comments" | "history"

export function DealActivity() {
  const { dealId } = useParams<{ dealId: string }>()
  const user = useAuthStore((s) => s.user)
  const isAdmin = user?.role === "admin"
  const { data: deal } = useDeal(dealId)
  const { data: activity, isLoading } = useDealActivity(isAdmin ? dealId : undefined)
  const [pane, setPane] = useState<Pane>("all")

  if (!dealId || !deal) return null

  // PRD F3: a closed deal is read-only, comments included.
  const dealClosed = deal.stage === "successful" || deal.stage === "dropped"
  const panes: { id: Pane; label: string }[] = isAdmin
    ? [
        { id: "all", label: "All" },
        { id: "comments", label: "Comments" },
        { id: "history", label: "History" },
      ]
    : []

  const showComments = !isAdmin || pane === "all" || pane === "comments"
  const showHistory = isAdmin && (pane === "all" || pane === "history")

  return (
    <div className="px-6 py-6">
      <DealHeader deal={deal} />

      {panes.length > 0 && (
        <div className="mb-4 flex gap-4">
          {panes.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setPane(p.id)}
              className={cn(
                "border-b-2 pb-1 text-body-strong",
                pane === p.id
                  ? "border-brand-600 text-brand-700"
                  : "border-transparent text-text-secondary hover:text-text-primary",
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
      )}

      <div className="flex gap-6">
        {showComments && (
          <section className={cn("min-w-0", showHistory ? "flex-1" : "max-w-[720px] flex-1")}>
            <h2 className="mb-2 text-label text-text-tertiary">Comments</h2>
            <CommentThread dealId={dealId} readOnly={dealClosed} />
          </section>
        )}

        {showHistory && (
          <section className="min-w-0 flex-1">
            <h2 className="mb-2 text-label text-text-tertiary">History</h2>
            <div className="rounded-md border border-border">
              <ActivityFeed items={activity} isLoading={isLoading} />
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
