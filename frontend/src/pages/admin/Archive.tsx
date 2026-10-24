import { useMemo, useState } from "react"
import {
  RETENTION_CHOICES,
  RETENTION_LABEL,
  useArchive,
  usePurgeDocument,
  useRestoreDocument,
  useSettings,
  useUpdateSettings,
} from "@/api/admin"
import { documentDownloadUrl } from "@/api/documents"
import { Button } from "@/components/ui/button"
import { PageBody } from "@/components/PageBody"
import { TableFooter } from "@/components/TableFooter"
import { PageHeader } from "@/components/PageHeader"
import { TabBand } from "@/components/TabBand"
import { Dialog, DialogFooter } from "@/components/ui/dialog"
import { RowMenu, RowMenuItem } from "@/components/ui/dropdown-menu"
import { cn, daysLeft, formatDate } from "@/lib/utils"
import type { ArchiveItem } from "@/api/types"

function PurgeDialog({
  item,
  onOpenChange,
  onConfirm,
  pending,
}: {
  item: ArchiveItem | null
  onOpenChange: (v: boolean) => void
  onConfirm: () => void
  pending: boolean
}) {
  if (!item) return null
  return (
    <Dialog open onOpenChange={onOpenChange} title={`Permanently delete '${item.display_name}'?`} width={440}>
      <p className="text-body text-text-secondary">
        The file will be removed from storage and cannot be recovered. The record of who uploaded and
        deleted it is kept.
      </p>
      <DialogFooter>
        <Button variant="secondary" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button variant="destructive" loading={pending} onClick={onConfirm}>
          Delete file
        </Button>
      </DialogFooter>
    </Dialog>
  )
}

function RetentionDialog({
  open,
  onOpenChange,
  current,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  current: number | null
}) {
  const updateSettings = useUpdateSettings()
  const [choice, setChoice] = useState<number | null>(current)

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="How long should the Archive keep files?" width={440}>
      <p className="mb-3 text-body text-text-secondary">
        Files past this age are removed from storage for good. The record of who uploaded and
        deleted them is always kept.
      </p>
      <div className="flex flex-col gap-1">
        {RETENTION_CHOICES.map((option) => (
          <label
            key={String(option.value)}
            className="flex h-9 cursor-pointer items-center gap-2 rounded-md px-2 text-body text-text-primary hover:bg-surface-hover"
          >
            <input
              type="radio"
              name="retention"
              checked={choice === option.value}
              onChange={() => setChoice(option.value)}
            />
            {option.label}
          </label>
        ))}
      </div>
      <DialogFooter>
        <Button variant="secondary" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button
          loading={updateSettings.isPending}
          onClick={async () => {
            await updateSettings.mutateAsync({ archive_retention_days: choice })
            onOpenChange(false)
          }}
        >
          Save
        </Button>
      </DialogFooter>
    </Dialog>
  )
}

const CONTROL =
  "h-8 rounded-md border border-border bg-surface px-2 text-table text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-600"

type ArchiveFilters = { deal: string; folder: string; person: string; since: string; until: string }
const NO_FILTERS: ArchiveFilters = { deal: "", folder: "", person: "", since: "", until: "" }

export function Archive() {
  const { data: items, isLoading } = useArchive()
  const { data: settings } = useSettings()
  const restore = useRestoreDocument()
  const purge = usePurgeDocument()
  const [purgeTarget, setPurgeTarget] = useState<ArchiveItem | null>(null)
  const [retentionOpen, setRetentionOpen] = useState(false)
  const [filters, setFilters] = useState<ArchiveFilters>(NO_FILTERS)
  const [search, setSearch] = useState("")

  const all = items ?? []

  // The options come from what is actually in the Archive, not from every
  // deal and folder in the app: a filter that can only ever return
  // nothing is a filter worth leaving out.
  const options = useMemo(() => {
    const pick = (get: (i: ArchiveItem) => string | null) =>
      [...new Set(all.map(get).filter((v): v is string => !!v))].sort()
    return {
      deals: pick((i) => i.deal_name),
      folders: pick((i) => i.folder_name),
      people: pick((i) => i.deleted_by_name),
    }
  }, [all])

  // Client-side: the Archive is admin-only and bounded by retention, so
  // it is already on the page in full. A round trip per keystroke would
  // buy nothing.
  const rows = useMemo(() => {
    const q = search.trim().toLowerCase()
    return all.filter((i) => {
      if (filters.deal && i.deal_name !== filters.deal) return false
      if (filters.folder && i.folder_name !== filters.folder) return false
      if (filters.person && i.deleted_by_name !== filters.person) return false
      if (filters.since && i.deleted_at < filters.since) return false
      if (filters.until && i.deleted_at > filters.until) return false
      if (!q) return true
      return (
        i.display_name.toLowerCase().includes(q) ||
        (i.reason ?? "").toLowerCase().includes(q) ||
        i.deal_name.toLowerCase().includes(q) ||
        i.folder_name.toLowerCase().includes(q)
      )
    })
  }, [all, filters, search])

  const filtered = search.trim().length > 0 || Object.values(filters).some(Boolean)

  function set(patch: Partial<ArchiveFilters>) {
    setFilters((prev) => ({ ...prev, ...patch }))
  }

  const retention = settings?.archive_retention_days ?? null
  const retentionLabel = retention === null ? "Keep forever" : (RETENTION_LABEL[retention] ?? `${retention} days`)

  return (
    <>
      <PageHeader title="Archive" />
      <TabBand
        tabs={
          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Filter by deal"
              className={CONTROL}
              value={filters.deal}
              onChange={(e) => set({ deal: e.target.value })}
            >
              <option value="">All deals</option>
              {options.deals.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            <select
              aria-label="Filter by folder"
              className={CONTROL}
              value={filters.folder}
              onChange={(e) => set({ folder: e.target.value })}
            >
              <option value="">All folders</option>
              {options.folders.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
            <select
              aria-label="Filter by who deleted it"
              className={CONTROL}
              value={filters.person}
              onChange={(e) => set({ person: e.target.value })}
            >
              <option value="">Anyone</option>
              {options.people.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            <label className="flex items-center gap-1.5 text-meta text-text-tertiary">
              From
              <input
                type="date"
                aria-label="Deleted from"
                className={CONTROL}
                value={filters.since.slice(0, 10)}
                onChange={(e) => set({ since: e.target.value ? `${e.target.value}T00:00:00` : "" })}
              />
            </label>
            <label className="flex items-center gap-1.5 text-meta text-text-tertiary">
              To
              <input
                type="date"
                aria-label="Deleted to"
                className={CONTROL}
                // Inclusive of the chosen day — what a person means by
                // "to the 9th", not midnight at its start.
                value={filters.until.slice(0, 10)}
                onChange={(e) => set({ until: e.target.value ? `${e.target.value}T23:59:59` : "" })}
              />
            </label>
            {filtered && (
              <button
                type="button"
                onClick={() => {
                  setFilters(NO_FILTERS)
                  setSearch("")
                }}
                className="text-meta text-brand-700 hover:underline"
              >
                Clear filters
              </button>
            )}
          </div>
        }
        search={{ value: search, onChange: setSearch, placeholder: "Search deleted files" }}
      />
      <PageBody>
      <div className="mb-4 flex items-baseline justify-between">
        <p className="text-table text-text-tertiary">
          {retention === null
            ? "Files approved for deletion. Kept here until someone removes them."
            : `Files approved for deletion. Removed for good ${retentionLabel.toLowerCase()} after they land here.`}
        </p>
        {/* DESIGN.md §6.10: "A retention link sits at the right of the
            toolbar: Retention: Keep forever — Change." */}
        <p className="text-table text-text-tertiary">
          Retention: {retentionLabel} —{" "}
          <button type="button" className="text-brand-700 hover:underline" onClick={() => setRetentionOpen(true)}>
            Change
          </button>
        </p>
      </div>

      <div className="rounded-md border border-border">
        <table className="w-full">
          <thead>
            <tr className="h-9 bg-surface-sunken text-left text-label text-text-tertiary">
              <th className="px-4 font-medium">Name</th>
              <th className="px-4 font-medium">Deal</th>
              <th className="px-4 font-medium">Folder</th>
              <th className="px-4 font-medium">Deleted by</th>
              <th className="px-4 font-medium">Approved by</th>
              <th className="px-4 font-medium">Deleted on</th>
              <th className="px-4 font-medium">Time left</th>
              <th className="px-4 font-medium">Reason</th>
              <th className="w-10 px-2" />
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr className="h-10 border-t border-border">
                <td colSpan={9} className="px-4">
                  <div className="h-3 w-1/3 animate-pulse rounded bg-surface-sunken" />
                </td>
              </tr>
            )}
            {!isLoading && rows.length === 0 && (
              <tr>
                <td colSpan={9} className="px-4 py-10 text-center">
                  <p className="text-body-strong text-text-primary">
                    {filtered ? "Nothing matches these filters" : "Archive is empty"}
                  </p>
                  <p className="text-table text-text-secondary">
                    {filtered
                      ? "Try a wider date range or clear the filters."
                      : "Files you approve for deletion are kept here."}
                  </p>
                </td>
              </tr>
            )}
            {rows.map((item) => (
              <tr key={item.id} className="group h-10 border-t border-border hover:bg-surface-hover">
                <td className="px-4 text-table font-medium text-text-primary">{item.display_name}</td>
                <td className="px-4 text-table text-text-secondary">{item.deal_name}</td>
                <td className="px-4 text-table text-text-secondary">{item.folder_name}</td>
                <td className="px-4 text-table text-text-secondary">{item.deleted_by_name ?? "—"}</td>
                <td className="px-4 text-table text-text-secondary">{item.approved_by_name ?? "—"}</td>
                <td className="px-4 text-table text-text-secondary">{formatDate(item.deleted_at)}</td>
                <td
                  className={cn(
                    "px-4 text-table",
                    // Red only once it is close enough to act on. A month
                    // of red is a month of nothing standing out.
                    daysLeft(item.purge_after).urgent ? "text-text-danger" : "text-text-secondary",
                  )}
                >
                  {daysLeft(item.purge_after).label}
                </td>
                <td className="max-w-40 truncate px-4 text-meta text-text-tertiary">{item.reason ?? "—"}</td>
                <td className="w-10 px-2">
                  <RowMenu>
                    <RowMenuItem onSelect={() => window.open(documentDownloadUrl(item.deal_id, item.id), "_self")}>
                      Download
                    </RowMenuItem>
                    <RowMenuItem onSelect={() => restore.mutate(item.id)}>Restore</RowMenuItem>
                    <RowMenuItem danger onSelect={() => setPurgeTarget(item)}>
                      Delete permanently
                    </RowMenuItem>
                  </RowMenu>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <TableFooter count={rows.length} noun="file" />
      </div>

      <RetentionDialog open={retentionOpen} onOpenChange={setRetentionOpen} current={retention} />

      <PurgeDialog
        item={purgeTarget}
        onOpenChange={() => setPurgeTarget(null)}
        pending={purge.isPending}
        onConfirm={async () => {
          if (purgeTarget) {
            await purge.mutateAsync(purgeTarget.id)
            setPurgeTarget(null)
          }
        }}
      />
      </PageBody>
    </>
  )
}
