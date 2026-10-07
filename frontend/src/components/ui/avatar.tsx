import { avatarColor, initials } from "@/lib/utils"
import { cn } from "@/lib/utils"

// 24px with 11px/600 initials, or the 20px variant for inside table
// cells. The same circle was hand-rolled in the top bar, the comment
// thread, the activity feed and the approvals table, each with slightly
// different sizes and none of them tinted.
export function Avatar({
  name,
  id,
  size = 24,
  className,
}: {
  name: string
  /** Tints the circle. Falls back to hashing the name when there is no id. */
  id?: string | null | undefined
  size?: 20 | 24
  className?: string
}) {
  return (
    <span
      aria-hidden
      style={{ backgroundColor: avatarColor(id ?? name) }}
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full font-semibold text-text-primary",
        size === 24 ? "h-6 w-6 text-[11px]" : "h-5 w-5 text-[10px]",
        className,
      )}
    >
      {initials(name)}
    </span>
  )
}
