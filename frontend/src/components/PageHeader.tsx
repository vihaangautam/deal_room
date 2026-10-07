import type { ReactNode } from "react"

// DESIGN.md §4.3: "64px, --surface, 1px bottom border, 24px side padding.
// Left, two lines: breadcrumb in 12/400 --text-tertiary, then the title in
// 20/600 with the stage pill 8px after it where applicable. Right:
// secondary actions, then one primary action."
//
// Tabs are not here: they get their own 48px band (components/TabBand)
// so they can share the row with a search field.
// Every page used to render its title on the canvas with no band at all,
// so there was no line between the page's identity and its content, and
// each page spaced its own title differently.
export function PageHeader({
  breadcrumb,
  title,
  pill,
  actions,
}: {
  breadcrumb?: ReactNode
  title: ReactNode
  /** The deal stage pill, 8px after the title. */
  pill?: ReactNode
  actions?: ReactNode
}) {
  return (
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex h-16 max-w-content items-center justify-between gap-4 px-6">
        <div className="min-w-0">
          {breadcrumb && <div className="text-meta text-text-tertiary">{breadcrumb}</div>}
          <div className="flex items-center gap-2">
            <h1 className="truncate text-title-page text-text-primary">{title}</h1>
            {pill}
          </div>
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
    </header>
  )
}
