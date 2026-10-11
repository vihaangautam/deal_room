import { useState } from "react"
import { Navigate, useParams } from "react-router-dom"
import { useDeal, useDealActivity } from "@/api/deals"
import type { AuditFilters } from "@/api/admin"
import { useAuthStore } from "@/stores/auth"
import { ActivityFeed } from "@/components/ActivityFeed"
import { ActivityFilters } from "@/components/ActivityFilters"
import { DealHeader } from "@/components/DealHeader"
import { PageBody } from "@/components/PageBody"
import { TabBand } from "@/components/TabBand"
import { TableFooter } from "@/components/TableFooter"

// Just the history; the comment thread has its own tab (DealComments).
// PRD §7's permission matrix gives "View Archive / Activity" to admin
// alone, so the whole page is admin-only and the tab is hidden from
// everyone else rather than shown empty.
const PAGE_SIZE = 50 // DESIGN.md §6.11

export function DealActivity() {
  const { dealId } = useParams<{ dealId: string }>()
  const user = useAuthStore((s) => s.user)
  const isAdmin = user?.role === "admin"
  const { data: deal } = useDeal(dealId)
  const [filters, setFilters] = useState<AuditFilters>({})
  const [page, setPage] = useState(1)
  const { data: activity, isLoading } = useDealActivity(isAdmin ? dealId : undefined, {
    ...filters,
    limit: 200,
  })

  function set(patch: Partial<AuditFilters>) {
    setPage(1) // a narrower filter can leave the current page empty
    setFilters((prev) => {
      const next = { ...prev, ...patch }
      // An empty select means "no filter", not a filter on "".
      for (const key of Object.keys(next) as (keyof AuditFilters)[]) {
        if (!next[key]) delete next[key]
      }
      return next
    })
  }

  if (!dealId) return null

  // A member reaching this by URL gets the tab they can actually use,
  // rather than a page that renders nothing and looks broken.
  if (user && !isAdmin) return <Navigate to={`/deals/${dealId}/comments`} replace />

  if (!deal) return null

  const rows = activity ?? []
  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const pageRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const filtered = (Object.keys(filters) as (keyof AuditFilters)[]).some(
    (k) => k !== "limit" && filters[k],
  )

  return (
    <>
      <DealHeader deal={deal} />
      <TabBand
        tabs={
          <ActivityFilters
            filters={filters}
            onChange={set}
            onClear={() => {
              setFilters({})
              setPage(1)
            }}
          />
        }
      />
      <PageBody>
        <div className="overflow-hidden rounded-lg border border-border bg-surface">
          <ActivityFeed
            items={pageRows}
            isLoading={isLoading}
            emptyTitle={filtered ? "Nothing matches these filters" : "No activity yet"}
            emptyBody={
              filtered
                ? "Try a wider date range or clear the filters."
                : "Actions on this deal will be recorded here."
            }
          />
          <TableFooter
            count={rows.length}
            noun="entry"
            plural="entries"
            page={page}
            pageCount={pageCount}
            onPageChange={setPage}
          />
        </div>
      </PageBody>
    </>
  )
}
