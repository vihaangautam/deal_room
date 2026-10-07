import { forwardRef } from "react"
import type { InputHTMLAttributes } from "react"
import { cn } from "@/lib/utils"

// DESIGN.md §5.14
export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: boolean
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, error = false, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "h-9 w-full rounded-md border bg-surface-sunken px-3 text-body text-text-primary placeholder:text-text-tertiary",
        "focus:outline-none focus:ring-2 focus:ring-brand-600 focus:ring-offset-2",
        error ? "border-danger-700" : "border-border focus:border-border-strong",
        className,
      )}
      {...props}
    />
  ),
)
Input.displayName = "Input"
