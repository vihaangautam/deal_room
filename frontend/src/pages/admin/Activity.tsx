import { useState } from "react"
import { useAuditActions, useAuditLog, type AuditFilters } from "@/api/admin"
import { useDeals } from "@/api/deals"
import { useUsers } from "@/api/users"
import { ActivityFeed } from "@/components/ActivityFeed"
import { PageHeader } from "@/components/PageHeader"

// DESIGN.md §6.11: "Filters: Deal, Person, Action, Date range." The page
// previously showed the newest 50 rows of everything with no way to narrow
// them, which is most of what PRD F10 asks this screen for.
const SELECT_CLASS =
  "h-8 rounded-md border border-border bg-surface px-2 text-table text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-600"

export function Activity() {
  const [filters, setFilters] = useState<AuditFilters>({})
  const { data: logs, isLoading } = useAuditLog({ ...filters, limit: 200 })
  const { data: deals } = useDeals()
  const { data: users } = useUsers()
  const { data: actions } = useAuditActions()

  function set(patch: Partial<AuditFilters>) {
    setFilters((prev) => {
      const next = { ...prev, ...patch }
      // An empty select means "no filter", not a filter on "".
      for (const k of Object.keys(next) as (keyof AuditFilters)[]) {
        if (!next[k]) delete next[k]
      }
      return next
    })
  }

  const hasFilters = Object.keys(filters).length > 0

  return (
    <>
      <PageHeader title="Activity" />
      <div className="px-6 py-6">
      <p className="mb-4 text-table text-text-tertiary">
        Every action on every deal, oldest kept forever. Read-only.
      </p>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <select
          aria-label="Filter by deal"
          className={SELECT_CLASS}
          value={filters.dealId ?? ""}
          onChange={(e) => set({ dealId: e.target.value })}
        >
          <option value="">All deals</option>
          {deals?.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>

        <select
          aria-label="Filter by person"
          className={SELECT_CLASS}
          value={filters.actorId ?? ""}
          onChange={(e) => set({ actorId: e.target.value })}
        >
          <option value="">Anyone</option>
          {users?.map((u) => (
            <option key={u.id} value={u.id}>
              {u.display_name}
            </option>
          ))}
        </select>

        <select
          aria-label="Filter by action"
          className={SELECT_CLASS}
          value={filters.action ?? ""}
          onChange={(e) => set({ action: e.target.value })}
        >
          <option value="">Any action</option>
          {actions?.map((a) => (
            <option key={a} value={a}>
              {a.replace(/[._]/g, " ")}
            </option>
          ))}
        </select>

        <label className="flex items-center gap-1.5 text-meta text-text-tertiary">
          From
          <input
            type="date"
            className={SELECT_CLASS}
            value={filters.since?.slice(0, 10) ?? ""}
            onChange={(e) => set({ since: e.target.value ? `${e.target.value}T00:00:00` : "" })}
          />
        </label>
        <label className="flex items-center gap-1.5 text-meta text-text-tertiary">
          To
          <input
            type="date"
            className={SELECT_CLASS}
            value={filters.until?.slice(0, 10) ?? ""}
            onChange={(e) => set({ until: e.target.value ? `${e.target.value}T23:59:59` : "" })}
          />
        </label>

        {hasFilters && (
          <button
            type="button"
            onClick={() => setFilters({})}
            className="text-meta text-brand-700 hover:underline"
          >
            Clear filters
          </button>
        )}
      </div>

      <div className="rounded-md border border-border">
        <ActivityFeed
          items={logs}
          isLoading={isLoading}
          showDeal
          emptyTitle={hasFilters ? "Nothing matches these filters" : "No activity yet"}
          emptyBody={
            hasFilters
              ? "Try a wider date range or clear the filters."
              : "Actions across every deal will be recorded here."
          }
        />
      </div>
      </div>
    </>
  )
}
