import type { ReactNode } from "react"
import * as DropdownPrimitive from "@radix-ui/react-dropdown-menu"
import { MoreHorizontal } from "lucide-react"
import { cn } from "@/lib/utils"

// Any trigger, not just the row "•••". TaskDetail hand-rolled two
// poppers out of a useState and an absolutely-positioned div because this
// only came in the row-menu shape — and neither of them closed on an
// outside click or Escape, since that is the part you have to write
// yourself and Radix already has.
export function Menu({
  trigger,
  align = "start",
  children,
}: {
  trigger: ReactNode
  align?: "start" | "end"
  children: ReactNode
}) {
  return (
    <DropdownPrimitive.Root>
      <DropdownPrimitive.Trigger asChild>{trigger}</DropdownPrimitive.Trigger>
      <DropdownPrimitive.Portal>
        <DropdownPrimitive.Content
          align={align}
          sideOffset={4}
          className="z-50 max-h-60 min-w-[160px] overflow-y-auto rounded-md border border-border bg-surface py-1 shadow-[0_4px_12px_rgba(16,24,16,.08),0_0_0_1px_#E3E6E3]"
        >
          {children}
        </DropdownPrimitive.Content>
      </DropdownPrimitive.Portal>
    </DropdownPrimitive.Root>
  )
}

export function RowMenu({ children }: { children: ReactNode }) {
  return (
    <Menu
      align="end"
      trigger={
        <button
          type="button"
          aria-label="More actions"
          className="flex h-7 w-7 items-center justify-center rounded text-text-tertiary opacity-0 hover:bg-surface-hover group-hover:opacity-100 focus:opacity-100"
        >
          <MoreHorizontal className="h-4 w-4" />
        </button>
      }
    >
      {children}
    </Menu>
  )
}

export function RowMenuItem({
  onSelect,
  danger = false,
  children,
}: {
  onSelect: () => void
  danger?: boolean
  children: ReactNode
}) {
  return (
    <DropdownPrimitive.Item
      onSelect={onSelect}
      className={cn(
        "cursor-pointer px-3 py-1.5 text-body text-text-primary outline-none hover:bg-surface-hover",
        danger && "text-text-danger",
      )}
    >
      {children}
    </DropdownPrimitive.Item>
  )
}
