import type { ReactNode } from "react"

// DESIGN.md §4.3: "64px, --surface, 1px bottom border, 24px side padding.
// Left, two lines: breadcrumb in 12/400 --text-tertiary, then the title in
// 20/600 with the stage pill 8px after it where applicable. Right:
// secondary actions, then one primary action."
//
// Every page used to render its title on the canvas with no band at all,
// so there was no line between the page's identity and its content, and
// each page spaced its own title differently.
export function PageHeader({
  breadcrumb,
  title,
  pill,
  actions,
  tabs,
}: {
  breadcrumb?: ReactNode
  title: ReactNode
  /** The deal stage pill, 8px after the title. */
  pill?: ReactNode
  actions?: ReactNode
  /** Deal pages add a 40px tab row directly beneath (§4.3). */
  tabs?: ReactNode
}) {
  return (
    <header className="border-b border-border bg-surface px-6">
      <div className="flex h-16 items-center justify-between gap-4">
        <div className="min-w-0">
          {breadcrumb && <div className="text-meta text-text-tertiary">{breadcrumb}</div>}
          <div className="flex items-center gap-2">
            <h1 className="truncate text-title-page text-text-primary">{title}</h1>
            {pill}
          </div>
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
      {tabs && <div className="flex h-10 items-center gap-6">{tabs}</div>}
    </header>
  )
}
