import { useState } from "react"
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
import { Dialog, DialogFooter } from "@/components/ui/dialog"
import { RowMenu, RowMenuItem } from "@/components/ui/dropdown-menu"
import { formatDate } from "@/lib/utils"
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

export function Archive() {
  const { data: items, isLoading } = useArchive()
  const { data: settings } = useSettings()
  const restore = useRestoreDocument()
  const purge = usePurgeDocument()
  const [purgeTarget, setPurgeTarget] = useState<ArchiveItem | null>(null)
  const [retentionOpen, setRetentionOpen] = useState(false)

  const retention = settings?.archive_retention_days ?? null
  const retentionLabel = retention === null ? "Keep forever" : (RETENTION_LABEL[retention] ?? `${retention} days`)

  return (
    <>
      <PageHeader title="Archive" />
      <PageBody>
      <div className="mb-4 flex items-baseline justify-between">
        <p className="text-table text-text-tertiary">
          Files approved for deletion. Kept until you remove them under retention settings.
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
              <th className="px-4 font-medium">Reason</th>
              <th className="w-10 px-2" />
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr className="h-10 border-t border-border">
                <td colSpan={8} className="px-4">
                  <div className="h-3 w-1/3 animate-pulse rounded bg-surface-sunken" />
                </td>
              </tr>
            )}
            {!isLoading && (items?.length ?? 0) === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-10 text-center">
                  <p className="text-body-strong text-text-primary">Archive is empty</p>
                  <p className="text-table text-text-secondary">
                    Files you approve for deletion are kept here.
                  </p>
                </td>
              </tr>
            )}
            {items?.map((item) => (
              <tr key={item.id} className="h-10 border-t border-border hover:bg-surface-hover">
                <td className="px-4 text-table font-medium text-text-primary">{item.display_name}</td>
                <td className="px-4 text-table text-text-secondary">{item.deal_name}</td>
                <td className="px-4 text-table text-text-secondary">{item.folder_name}</td>
                <td className="px-4 text-table text-text-secondary">{item.deleted_by_name ?? "—"}</td>
                <td className="px-4 text-table text-text-secondary">{item.approved_by_name ?? "—"}</td>
                <td className="px-4 text-table text-text-secondary">{formatDate(item.deleted_at)}</td>
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
        <TableFooter count={items?.length ?? 0} noun="file" />
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
