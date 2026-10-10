import { useMemo, useState } from "react"
import { useApprovals, useBulkApprovalAction } from "@/api/approvals"
import { documentDownloadUrl } from "@/api/documents"
import { Avatar } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { RowMenu, RowMenuItem } from "@/components/ui/dropdown-menu"
import { PageBody } from "@/components/PageBody"
import { UseALaptop } from "@/components/UseALaptop"
import { UserName } from "@/components/UserName"
import { PageHeader } from "@/components/PageHeader"
import { Tab, TabBand } from "@/components/TabBand"
import { TableFooter } from "@/components/TableFooter"
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

// The queue's own tabs. "All" plus one per kind of request, each with its
// count — the two dropdowns these replace hid both the counts and the
// fact that anything was filtered at all.
const TYPE_TABS: { id: ApprovalType | "all"; label: string }[] = [
  { id: "all", label: "All" },
  { id: "document_upload", label: "Uploads" },
  { id: "document_delete", label: "Deletions" },
  { id: "task_reassign", label: "Reassignments" },
  { id: "task_delete", label: "Task deletions" },
]

export function Approvals() {
  const [typeFilter, setTypeFilter] = useState<ApprovalType | "all">("all")
  const [search, setSearch] = useState("")
  const { data: approvals, isLoading } = useApprovals()
  const bulkAction = useBulkApprovalAction()
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [rejectOpen, setRejectOpen] = useState(false)

  const all = approvals ?? []
  const countFor = (id: ApprovalType | "all") =>
    id === "all" ? all.length : all.filter((a) => a.type === id).length

  const rows = useMemo(() => {
    const byType = typeFilter === "all" ? all : all.filter((a) => a.type === typeFilter)
    const q = search.trim().toLowerCase()
    if (!q) return byType
    return byType.filter(
      (a) =>
        a.item_label.toLowerCase().includes(q) ||
        a.deal_name.toLowerCase().includes(q) ||
        a.requested_by_name.toLowerCase().includes(q),
    )
  }, [all, typeFilter, search])

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
    <>
      <PageHeader
        title="Approvals"
        pill={<span className="text-table text-text-tertiary">{rows.length} waiting</span>}
      />
      <TabBand
        tabs={TYPE_TABS.map((t) => (
          <Tab
            key={t.id}
            active={typeFilter === t.id}
            count={countFor(t.id)}
            onClick={() => {
              setTypeFilter(t.id)
              // Selections are per row; leaving them set while the visible
              // rows change would approve things the user can no longer see.
              setSelected(new Set())
            }}
          >
            {t.label}
          </Tab>
        ))}
        search={{ value: search, onChange: setSearch, placeholder: "Search requests" }}
      />

      <PageBody>
        <UseALaptop what="Approving in bulk needs a bigger screen. You can still read the queue here." />
        {selected.size > 0 && (
          <div className="mb-4 flex h-14 items-center gap-3 rounded-lg border border-border bg-brand-50 px-4 max-md:hidden">
            <span className="text-body-strong text-brand-700">{selected.size} selected</span>
            <span className="h-5 w-px bg-border" aria-hidden />
            <Button size="sm" onClick={approveSelected} loading={bulkAction.isPending}>
              Approve selected
            </Button>
            <Button size="sm" variant="secondary" className="text-text-danger" onClick={() => setRejectOpen(true)}>
              Reject selected
            </Button>
            <button
              type="button"
              className="ml-auto text-body-strong text-text-secondary hover:text-text-primary"
              onClick={() => setSelected(new Set())}
            >
              Clear selection
            </button>
          </div>
        )}

        <div className="overflow-hidden rounded-lg border border-border bg-surface">
        <table className="w-full">
          <thead>
            <tr className="h-9 bg-surface-sunken text-left text-label text-text-tertiary">
              <th className="w-10 px-4 max-md:hidden">
                <input
                  type="checkbox"
                  checked={rows.length > 0 && selected.size === rows.length}
                  // Some-but-not-all is its own state; without it the box
                  // reads as "nothing selected" while two rows are.
                  ref={(el) => {
                    if (el) el.indeterminate = selected.size > 0 && selected.size < rows.length
                  }}
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
              <th className="w-10 px-2" />
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
        <TableFooter count={rows.length} noun="request" />
      </div>

        <RejectDialog
        open={rejectOpen}
        onOpenChange={setRejectOpen}
        count={selected.size}
        pending={bulkAction.isPending}
          onConfirm={rejectSelected}
        />
      </PageBody>
    </>
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
        {/* DESIGN.md §5.8: "Item for a document: filename in 13/500 as a
            download link". Approving a file you cannot open is a guess,
            which is what that section says in as many words. Task rows
            have nothing to download, so they stay plain text. */}
        {row.document_id ? (
          <a
            href={documentDownloadUrl(row.deal_id, row.document_id)}
            className="text-table font-medium text-text-primary hover:underline"
          >
            {row.item_label}
          </a>
        ) : (
          <p className="text-table font-medium text-text-primary">{row.item_label}</p>
        )}
        {row.item_sublabel && <p className="text-meta text-text-tertiary">{row.item_sublabel}</p>}
      </td>
      <td className="px-4 text-table text-text-secondary">{row.deal_name}</td>
      <td className="px-4 text-table text-text-secondary">
        <span className="flex items-center gap-2">
          <Avatar name={row.requested_by_name} size={20} />
          <UserName name={row.requested_by_name} />
        </span>
      </td>
      <td className="px-4 text-meta text-text-tertiary">{formatDateTime(row.requested_at)}</td>
      <td className="max-w-48 truncate px-4 text-meta text-text-tertiary" title={row.note ?? undefined}>
        {row.note ?? "—"}
      </td>
      <td className="w-10 px-2">
        {row.document_id && (
          <RowMenu>
            <RowMenuItem
              onSelect={() => window.open(documentDownloadUrl(row.deal_id, row.document_id!), "_self")}
            >
              Download
            </RowMenuItem>
          </RowMenu>
        )}
      </td>
    </tr>
  )
}
