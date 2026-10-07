import type { ReactNode } from "react"
import { Search } from "lucide-react"
import { cn } from "@/lib/utils"

// 48px white band under the page header, 1px bottom border: tabs on the
// left, search on the right, same row. A search input sitting alone in
// its own band is the single thing that made the first build feel loose,
// and nothing is allowed to float on the canvas — the canvas starts below
// this.
export function TabBand({
  tabs,
  search,
  trailing,
}: {
  tabs?: ReactNode
  /** Right-aligned search. 32px tall so it fits the 48px band. */
  search?: { value: string; onChange: (v: string) => void; placeholder: string }
  /** Anything else on the right, before the search. */
  trailing?: ReactNode
}) {
  return (
    <div className="border-b border-border bg-surface">
      <div className="mx-auto flex h-12 max-w-content items-center gap-4 px-6">
      <div className="flex h-full flex-1 items-center gap-6">{tabs}</div>
      {trailing}
      {search && (
        <div className="relative w-60">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-tertiary"
            aria-hidden
          />
          <input
            value={search.value}
            onChange={(e) => search.onChange(e.target.value)}
            placeholder={search.placeholder}
            aria-label={search.placeholder}
            className="h-8 w-full rounded-md border border-border bg-surface-sunken pl-8 pr-2 text-table text-text-primary placeholder:text-text-tertiary focus:outline-none focus:ring-2 focus:ring-brand-600"
          />
          </div>
        )}
      </div>
    </div>
  )
}

export function Tab({
  active,
  count,
  onClick,
  children,
}: {
  active: boolean
  count?: number
  onClick?: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex h-full items-center gap-1.5 border-b-2 text-body-strong",
        active
          ? "border-brand-600 text-brand-700"
          : "border-transparent text-text-secondary hover:text-text-primary",
      )}
    >
      {children}
      {count !== undefined && (
        <span className="text-meta font-normal text-text-tertiary">{count}</span>
      )}
    </button>
  )
}
