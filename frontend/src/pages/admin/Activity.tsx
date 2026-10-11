import { useState } from "react"
import { useAuditLog, type AuditFilters } from "@/api/admin"
import { ActivityFeed } from "@/components/ActivityFeed"
import { ActivityFilters } from "@/components/ActivityFilters"
import { PageBody } from "@/components/PageBody"
import { TabBand } from "@/components/TabBand"
import { useDebounced } from "@/hooks/useDebounced"
import { TableFooter } from "@/components/TableFooter"
import { PageHeader } from "@/components/PageHeader"

// DESIGN.md §6.11: "Filters: Deal, Person, Action, Date range." The page
// previously showed the newest 50 rows of everything with no way to narrow
// them, which is most of what PRD F10 asks this screen for.
const PAGE_SIZE = 50 // DESIGN.md §6.11


export function Activity() {
  const [filters, setFilters] = useState<AuditFilters>({})
  const [search, setSearch] = useState("")
  const [page, setPage] = useState(1)
  const debouncedSearch = useDebounced(search)
  const { data: logs, isLoading } = useAuditLog({
    ...filters,
    ...(debouncedSearch.trim() ? { q: debouncedSearch.trim() } : {}),
    limit: 200,
  })

  function set(patch: Partial<AuditFilters>) {
    setFilters((prev) => {
      const next = { ...prev, ...patch }
      setPage(1) // a narrower filter can leave the current page empty
      // An empty select means "no filter", not a filter on "".
      for (const k of Object.keys(next) as (keyof AuditFilters)[]) {
        if (!next[k]) delete next[k]
      }
      return next
    })
  }

  const rows = logs ?? []
  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const pageRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const hasFilters = debouncedSearch.trim().length > 0 || Object.keys(filters).length > 0

  return (
    <>
      <PageHeader title="Activity" />
      <TabBand
        tabs={
          <ActivityFilters
            filters={filters}
            onChange={set}
            onClear={() => {
              setFilters({})
              setSearch("")
              setPage(1)
            }}
            showDeal
          />
        }
        search={{
          value: search,
          onChange: (v) => {
            setSearch(v)
            setPage(1)
          },
          placeholder: "Search all activity",
        }}
      />
      <PageBody>
      <p className="mb-4 text-table text-text-tertiary">
        Every action on every deal, oldest kept forever. Read-only.
      </p>

      <div className="overflow-hidden rounded-lg border border-border bg-surface">
        <ActivityFeed
          items={pageRows}
          isLoading={isLoading}
          showDeal
          emptyTitle={hasFilters ? "Nothing matches these filters" : "No activity yet"}
          emptyBody={
            hasFilters
              ? "Try a wider date range or clear the filters."
              : "Actions across every deal will be recorded here."
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
