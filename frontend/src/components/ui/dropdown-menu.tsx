import type { ReactNode } from "react"
import * as DropdownPrimitive from "@radix-ui/react-dropdown-menu"
import { MoreHorizontal } from "lucide-react"
import { cn } from "@/lib/utils"

export function RowMenu({ children }: { children: ReactNode }) {
  return (
    <DropdownPrimitive.Root>
      <DropdownPrimitive.Trigger asChild>
        <button
          type="button"
          aria-label="More actions"
          className="flex h-7 w-7 items-center justify-center rounded text-text-tertiary opacity-0 hover:bg-surface-hover group-hover:opacity-100 focus:opacity-100"
        >
          <MoreHorizontal className="h-4 w-4" />
        </button>
      </DropdownPrimitive.Trigger>
      <DropdownPrimitive.Portal>
        <DropdownPrimitive.Content
          align="end"
          sideOffset={4}
          className="z-50 min-w-[160px] rounded-md border border-border bg-surface py-1 shadow-[0_4px_12px_rgba(16,24,16,.08),0_0_0_1px_#E3E6E3]"
        >
          {children}
        </DropdownPrimitive.Content>
      </DropdownPrimitive.Portal>
    </DropdownPrimitive.Root>
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
