import { useMemo, useState } from "react"
import { useApprovals, useBulkApprovalAction } from "@/api/approvals"
import { Button } from "@/components/ui/button"
import { toast } from "@/components/ui/toast"
import { Dialog, DialogFooter } from "@/components/ui/dialog"
import { formatDateTime } from "@/lib/utils"
import type { ApprovalItem, ApprovalType } from "@/api/types"

const TYPE_LABEL: Record<ApprovalType, string> = {
  document_upload: "Upload",
  document_delete: "Deletion",
  task_reassign: "Reassign",
  task_delete: "Delete task",
}

function RejectDialog({
  open,
  onOpenChange,
  count,
  onConfirm,
  pending,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  count: number
  onConfirm: (note: string) => void
  pending: boolean
}) {
  const [note, setNote] = useState("")
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={`Reject ${count} request${count === 1 ? "" : "s"}?`} width={440}>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Reason (shown to the requester)"
        className="h-20 w-full rounded-md border border-border bg-surface-sunken p-2 text-body focus:outline-none focus:ring-2 focus:ring-brand-600"
      />
      <DialogFooter>
        <Button variant="secondary" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button variant="destructive" loading={pending} onClick={() => onConfirm(note)}>
          Reject
        </Button>
      </DialogFooter>
    </Dialog>
  )
}

export function Approvals() {
  const [typeFilter, setTypeFilter] = useState<ApprovalType | "">("")
  const [dealFilter, setDealFilter] = useState("")
  const { data: approvals, isLoading } = useApprovals({ type: typeFilter || undefined })
  const bulkAction = useBulkApprovalAction()
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [rejectOpen, setRejectOpen] = useState(false)

  const deals = useMemo(() => {
    const names = new Set((approvals ?? []).map((a) => a.deal_name))
    return Array.from(names)
  }, [approvals])

  const rows = useMemo(
    () => (dealFilter ? (approvals ?? []).filter((a) => a.deal_name === dealFilter) : (approvals ?? [])),
    [approvals, dealFilter],
  )

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleAll() {
    setSelected((prev) => (prev.size === rows.length ? new Set() : new Set(rows.map((r) => r.id))))
  }

  async function approveSelected() {
    const result = await bulkAction.mutateAsync({ ids: Array.from(selected), action: "approve" })
    setSelected(new Set())
    // DESIGN.md §5.11: "16 approved." or "15 approved, 1 already
    // handled by Samir" — the per-item result, not a generic success.
    toast(
      result.already_handled > 0
        ? `${result.approved} approved, ${result.already_handled} already handled by someone else`
        : `${result.approved} approved.`,
    )
  }

  async function rejectSelected(note: string) {
    const result = await bulkAction.mutateAsync({ ids: Array.from(selected), action: "reject", note })
    setSelected(new Set())
    setRejectOpen(false)
    toast(`${result.rejected} rejected.`)
  }

  return (
    <div className="px-6 py-6">
      <div className="mb-4 flex items-baseline gap-2">
        <h1 className="text-title-page text-text-primary">Approvals</h1>
        <span className="text-table text-text-tertiary">{rows.length} waiting</span>
      </div>

      <div className="rounded-md border border-border">
        {selected.size > 0 ? (
          <div className="flex h-11 items-center gap-3 border-b border-border bg-brand-50 px-4">
            <span className="text-body-strong text-brand-700">{selected.size} selected</span>
            <Button size="sm" onClick={approveSelected} loading={bulkAction.isPending}>
              Approve selected
            </Button>
            <Button size="sm" variant="destructive" onClick={() => setRejectOpen(true)}>
              Reject selected
            </Button>
            <button
              type="button"
              className="ml-auto text-meta text-text-tertiary hover:text-text-secondary"
              onClick={() => setSelected(new Set())}
            >
              Clear selection
            </button>
          </div>
        ) : (
          <div className="flex h-11 items-center gap-2 border-b border-border px-4">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value as ApprovalType | "")}
              className="h-8 rounded-md border border-border bg-surface px-2 text-table"
            >
              <option value="">All types</option>
              <option value="document_upload">Upload</option>
              <option value="document_delete">Deletion</option>
              <option value="task_reassign">Reassign</option>
              <option value="task_delete">Delete task</option>
            </select>
            <select
              value={dealFilter}
              onChange={(e) => setDealFilter(e.target.value)}
              className="h-8 rounded-md border border-border bg-surface px-2 text-table"
            >
              <option value="">All deals</option>
              {deals.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>
        )}

        <table className="w-full">
          <thead>
            <tr className="h-9 bg-surface-sunken text-left text-label text-text-tertiary">
              <th className="w-10 px-4">
                <input
                  type="checkbox"
                  checked={rows.length > 0 && selected.size === rows.length}
                  onChange={toggleAll}
                  aria-label="Select all"
                />
              </th>
              <th className="px-4 font-medium">Type</th>
              <th className="px-4 font-medium">Item</th>
              <th className="px-4 font-medium">Deal</th>
              <th className="px-4 font-medium">Requested by</th>
              <th className="px-4 font-medium">Requested on</th>
              <th className="px-4 font-medium">Note</th>
            </tr>
          </thead>
          <tbody>
            {isLoading &&
              [0, 1].map((i) => (
                <tr key={i} className="h-9 border-t border-border">
                  <td colSpan={7} className="px-4">
                    <div className="h-3 w-1/3 animate-pulse rounded bg-surface-sunken" />
                  </td>
                </tr>
              ))}
            {!isLoading && rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center">
                  <p className="text-body-strong text-text-primary">Nothing waiting for approval</p>
                  <p className="text-table text-text-secondary">
                    New uploads, deletions and reassignments will appear here.
                  </p>
                </td>
              </tr>
            )}
            {rows.map((row) => (
              <Row key={row.id} row={row} checked={selected.has(row.id)} onToggle={() => toggle(row.id)} />
            ))}
          </tbody>
        </table>
      </div>

      <RejectDialog
        open={rejectOpen}
        onOpenChange={setRejectOpen}
        count={selected.size}
        pending={bulkAction.isPending}
        onConfirm={rejectSelected}
      />
    </div>
  )
}

function Row({ row, checked, onToggle }: { row: ApprovalItem; checked: boolean; onToggle: () => void }) {
  return (
    <tr className="h-9 border-t border-border hover:bg-surface-hover">
      <td className="px-4">
        <input type="checkbox" checked={checked} onChange={onToggle} aria-label={`Select ${row.item_label}`} />
      </td>
      <td className="px-4 text-table text-text-primary">{TYPE_LABEL[row.type]}</td>
      <td className="px-4">
        <p className="text-table font-medium text-text-primary">{row.item_label}</p>
        {row.item_sublabel && <p className="text-meta text-text-tertiary">{row.item_sublabel}</p>}
      </td>
      <td className="px-4 text-table text-text-secondary">{row.deal_name}</td>
      <td className="px-4 text-table text-text-secondary">{row.requested_by_name}</td>
      <td className="px-4 text-meta text-text-tertiary">{formatDateTime(row.requested_at)}</td>
      <td className="max-w-48 truncate px-4 text-meta text-text-tertiary" title={row.note ?? undefined}>
        {row.note ?? "—"}
      </td>
    </tr>
  )
}
