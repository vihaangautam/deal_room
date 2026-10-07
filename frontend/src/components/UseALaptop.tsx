// Below 768px the app is read and download only (DESIGN §9). The three
// things that genuinely cannot work at that width say so instead of
// rendering a layout that falls apart: a multi-file upload with per-file
// progress, the permission matrix, and bulk approvals.
export function UseALaptop({ what }: { what: string }) {
  return (
    <div className="hidden rounded-md border border-border bg-surface px-4 py-6 text-center max-md:block">
      <p className="text-body-strong text-text-primary">Use a laptop for this</p>
      <p className="text-table text-text-secondary">{what}</p>
    </div>
  )
}
