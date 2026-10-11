import { useAuditActions, type AuditFilters } from "@/api/admin"
import { useDeals } from "@/api/deals"
import { useUsers } from "@/api/users"

// DESIGN.md §6.11's filter set — Deal, Person, Action, Date range — shared
// by the admin Activity page and a deal's own Activity tab. The deal tab
// hides the Deal filter because the page already is one.
//
// One component rather than two copies: these are the same four questions
// wherever you ask them, and a second copy is how the two screens drift
// into behaving differently.
const CONTROL =
  "h-8 rounded-md border border-border bg-surface px-2 text-table text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-600"

export function ActivityFilters({
  filters,
  onChange,
  onClear,
  showDeal = false,
}: {
  filters: AuditFilters
  onChange: (patch: Partial<AuditFilters>) => void
  onClear: () => void
  showDeal?: boolean
}) {
  const { data: deals } = useDeals()
  const { data: users } = useUsers()
  const { data: actions } = useAuditActions()

  // `limit` is not a filter the user set, so it must not light up "Clear".
  const active = (Object.keys(filters) as (keyof AuditFilters)[]).filter(
    (k) => k !== "limit" && filters[k],
  )

  return (
    <div className="flex flex-wrap items-center gap-2">
      {showDeal && (
        <select
          aria-label="Filter by deal"
          className={CONTROL}
          value={filters.dealId ?? ""}
          onChange={(e) => onChange({ dealId: e.target.value })}
        >
          <option value="">All deals</option>
          {deals?.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
      )}

      <select
        aria-label="Filter by person"
        className={CONTROL}
        value={filters.actorId ?? ""}
        onChange={(e) => onChange({ actorId: e.target.value })}
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
        className={CONTROL}
        value={filters.action ?? ""}
        onChange={(e) => onChange({ action: e.target.value })}
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
          aria-label="From date"
          className={CONTROL}
          value={filters.since?.slice(0, 10) ?? ""}
          onChange={(e) => onChange({ since: e.target.value ? `${e.target.value}T00:00:00` : "" })}
        />
      </label>
      <label className="flex items-center gap-1.5 text-meta text-text-tertiary">
        To
        <input
          type="date"
          aria-label="To date"
          className={CONTROL}
          // Inclusive of the chosen day, which is what a person means by
          // "to the 9th" — not midnight at its start.
          value={filters.until?.slice(0, 10) ?? ""}
          onChange={(e) => onChange({ until: e.target.value ? `${e.target.value}T23:59:59` : "" })}
        />
      </label>

      {active.length > 0 && (
        <button type="button" onClick={onClear} className="text-meta text-brand-700 hover:underline">
          Clear filters
        </button>
      )}
    </div>
  )
}
