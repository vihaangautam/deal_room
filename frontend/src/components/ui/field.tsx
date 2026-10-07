import type { ReactNode } from "react"
import * as LabelPrimitive from "@radix-ui/react-label"

// DESIGN.md §5.14: label above (14/500), 6px gap, helper or error below.
// Required fields carry no asterisk; optional ones get "(optional)".
export function Field({
  label,
  htmlFor,
  optional = false,
  error,
  helper,
  children,
}: {
  label: string
  htmlFor: string
  optional?: boolean
  error?: string
  helper?: string
  children: ReactNode
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <LabelPrimitive.Root htmlFor={htmlFor} className="text-body-strong text-text-primary">
        {label}
        {optional && <span className="text-text-tertiary"> (optional)</span>}
      </LabelPrimitive.Root>
      {children}
      {error ? (
        <p className="text-meta text-text-danger">{error}</p>
      ) : helper ? (
        <p className="text-meta text-text-tertiary">{helper}</p>
      ) : null}
    </div>
  )
}
