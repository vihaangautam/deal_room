import { ChevronLeft, ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"

// 40px row closing every table card: the result count on the left,
// pagination on the right. The count lives here and nowhere else — it used
// to sit above the table, which put it in a different place on each page
// and made it read as a toolbar label rather than a result.
//
// Whatever the count says must be counted the same way as every other
// number on the screen; anything counted differently gets its own label.
export function TableFooter({
  count,
  noun,
  page,
  pageCount,
  onPageChange,
}: {
  count: number
  /** Singular noun: "deal" renders "3 deals", "1 deal". */
  noun: string
  page?: number
  pageCount?: number
  onPageChange?: (page: number) => void
}) {
  const paginated = page !== undefined && pageCount !== undefined && onPageChange !== undefined

  return (
    <div className="flex h-10 items-center justify-between border-t border-border px-4">
      <span className="text-meta text-text-tertiary">
        {count} {count === 1 ? noun : `${noun}s`}
      </span>
      {paginated && pageCount > 1 && (
        <div className="flex items-center gap-1">
          <span className="mr-2 text-meta text-text-tertiary">
            Page {page} of {pageCount}
          </span>
          <PageButton
            label="Previous page"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            <ChevronLeft className="h-4 w-4" aria-hidden />
          </PageButton>
          <PageButton
            label="Next page"
            disabled={page >= pageCount}
            onClick={() => onPageChange(page + 1)}
          >
            <ChevronRight className="h-4 w-4" aria-hidden />
          </PageButton>
        </div>
      )}
    </div>
  )
}

function PageButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string
  disabled: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "flex h-7 w-7 items-center justify-center rounded-md border border-border-strong text-text-secondary",
        disabled ? "cursor-not-allowed opacity-40" : "hover:bg-surface-sunken",
      )}
    >
      {children}
    </button>
  )
}
