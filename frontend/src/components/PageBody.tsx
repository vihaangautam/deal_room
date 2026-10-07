import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

// Everything below the header and tab bands: canvas background, 24px
// gutters, capped at 1400px and centred. One component so a page cannot
// quietly pick its own width — which is how the Deals table ended up a
// different width from the Documents table.
export function PageBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("mx-auto max-w-content px-6 py-6", className)}>{children}</div>
}
