import { useRef, useState } from "react"
import { GripVertical, Plus } from "lucide-react"
import {
  isFolderDeleteBlocked,
  useCreateFolder,
  useDeleteFolder,
  useFolders,
  useRenameFolder,
  useReorderFolders,
} from "@/api/folders"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/PageHeader"
import { Input } from "@/components/ui/input"
import { Field } from "@/components/ui/field"
import { Dialog, DialogFooter } from "@/components/ui/dialog"
import { RowMenu, RowMenuItem } from "@/components/ui/dropdown-menu"
import { toast } from "@/components/ui/toast"
import { cn } from "@/lib/utils"
import type { Folder } from "@/api/types"

function AddFolderDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const createFolder = useCreateFolder()
  const [name, setName] = useState("")
  const [defaultAccess, setDefaultAccess] = useState<"none" | "view">("none")

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    await createFolder.mutateAsync({ name, default_access: defaultAccess })
    setName("")
    setDefaultAccess("none")
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Add folder" width={440}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Field label="Name" htmlFor="folder-name">
          <Input id="folder-name" required value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field
          label="Starting access for members"
          htmlFor="default-access"
          helper="New folders start with None access by default. Samir can change access to View or Contribute per person in Users & permissions."
        >
          <div className="flex gap-4">
            <label className="flex items-center gap-1.5 text-body text-text-primary">
              <input
                type="radio"
                name="starting-access"
                checked={defaultAccess === "none"}
                onChange={() => setDefaultAccess("none")}
              />
              None
            </label>
            <label className="flex items-center gap-1.5 text-body text-text-primary">
              <input
                type="radio"
                name="starting-access"
                checked={defaultAccess === "view"}
                onChange={() => setDefaultAccess("view")}
              />
              View
            </label>
          </div>
        </Field>
        <DialogFooter>
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" loading={createFolder.isPending}>
            Save
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  )
}

function BlockedDialog({
  open,
  onOpenChange,
  message,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  message: string
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Can't delete folder" width={440}>
      <p className="text-body text-text-secondary">{message}</p>
      <DialogFooter>
        <Button variant="secondary" onClick={() => onOpenChange(false)}>
          Close
        </Button>
      </DialogFooter>
    </Dialog>
  )
}

function FolderRow({
  folder,
  dragging,
  onDragStart,
  onDragEnter,
  onDragEnd,
}: {
  folder: Folder
  dragging: boolean
  onDragStart: () => void
  onDragEnter: () => void
  onDragEnd: () => void
}) {
  const rename = useRenameFolder()
  const deleteFolder = useDeleteFolder()
  const [renaming, setRenaming] = useState(false)
  const [name, setName] = useState(folder.name)
  const [blockedMessage, setBlockedMessage] = useState<string | null>(null)
  // DESIGN.md §5.13 wants a confirmation on every destructive action, and
  // "Delete" went straight through: a folder is part of every deal, so
  // one stray click removed a row from all of them.
  const [confirmOpen, setConfirmOpen] = useState(false)

  function saveRename() {
    if (name.trim() && name !== folder.name) rename.mutate({ folderId: folder.id, name: name.trim() })
    setRenaming(false)
  }

  async function handleDelete() {
    try {
      await deleteFolder.mutateAsync(folder.id)
    } catch (err) {
      if (isFolderDeleteBlocked(err)) {
        setBlockedMessage(err.detail.message)
      }
    }
  }

  return (
    <tr
      draggable={!renaming}
      onDragStart={onDragStart}
      onDragEnter={onDragEnter}
      onDragOver={(e) => e.preventDefault()}
      onDragEnd={onDragEnd}
      onDrop={(e) => e.preventDefault()}
      className={cn(
        "h-10 border-t border-border hover:bg-surface-hover",
        dragging && "opacity-40",
      )}
    >
      <td className="w-8 px-2">
        <GripVertical
          className="h-4 w-4 cursor-grab text-text-tertiary active:cursor-grabbing"
          aria-hidden
        />
      </td>
      <td className="px-4">
        {renaming ? (
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={saveRename}
            onKeyDown={(e) => {
              if (e.key === "Enter") saveRename()
              if (e.key === "Escape") setRenaming(false)
            }}
            className="h-8 w-64 rounded border border-border-strong bg-surface px-2 text-table"
          />
        ) : (
          <span className="text-table font-medium text-text-primary">{folder.name}</span>
        )}
      </td>
      <td className="w-10 px-2">
        <RowMenu>
          <RowMenuItem onSelect={() => setRenaming(true)}>Rename</RowMenuItem>
          <RowMenuItem danger onSelect={() => setConfirmOpen(true)}>
            Delete
          </RowMenuItem>
        </RowMenu>
      </td>

      <Dialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={`Delete the ${folder.name} folder?`}
        width={440}
      >
        <p className="text-body text-text-secondary">
          It will stop appearing in every deal. Folders holding files can't be deleted, so nothing
          is lost — but you'll have to add it again to get it back.
        </p>
        <DialogFooter>
          <Button variant="secondary" onClick={() => setConfirmOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            loading={deleteFolder.isPending}
            onClick={async () => {
              setConfirmOpen(false)
              await handleDelete()
            }}
          >
            Delete folder
          </Button>
        </DialogFooter>
      </Dialog>

      <BlockedDialog
        open={blockedMessage !== null}
        onOpenChange={() => setBlockedMessage(null)}
        message={blockedMessage ?? ""}
      />
    </tr>
  )
}

export function Folders() {
  const { data: folders, isLoading } = useFolders()
  const reorder = useReorderFolders()
  const [addOpen, setAddOpen] = useState(false)
  // The list is reordered locally as the row is dragged and saved once on
  // drop; `dragOrder` is null whenever nothing is being dragged, so the
  // server's order stays the source of truth the rest of the time.
  //
  // The drag position and the working list live in refs, not state,
  // because dragstart and dragenter can both land before React commits a
  // render — a quick drag then reads a stale index out of the handler's
  // closure and moves nothing. State here only drives the dimmed row.
  const dragFrom = useRef<number | null>(null)
  const pendingOrder = useRef<Folder[] | null>(null)
  const [dragOrder, setDragOrder] = useState<Folder[] | null>(null)
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null)

  const ordered = dragOrder ?? folders ?? []

  function startDrag(index: number) {
    dragFrom.current = index
    pendingOrder.current = [...(folders ?? [])]
    setDraggingIndex(index)
  }

  function moveTo(index: number) {
    const from = dragFrom.current
    if (from === null || from === index) return
    const next = [...(pendingOrder.current ?? folders ?? [])]
    const [moved] = next.splice(from, 1)
    if (!moved) return
    next.splice(index, 0, moved)
    pendingOrder.current = next
    dragFrom.current = index
    setDragOrder(next)
    setDraggingIndex(index)
  }

  function commitOrder() {
    const moving = pendingOrder.current
    pendingOrder.current = null
    dragFrom.current = null
    setDraggingIndex(null)
    setDragOrder(null)
    if (!moving) return
    // Nothing actually moved — a click on the handle, or a drag back to
    // where it started.
    if (moving.map((f) => f.id).join() === (folders ?? []).map((f) => f.id).join()) return
    reorder.mutate(
      moving.map((f) => f.id),
      { onSuccess: () => toast("Folder order saved.") },
    )
  }

  return (
    <>
      <PageHeader
        title="Folders"
        actions={
          <Button onClick={() => setAddOpen(true)}>
            <Plus className="h-4 w-4" />
            Add folder
          </Button>
        }
      />
      <div className="px-6 py-6">
      <p className="mb-4 text-table text-text-tertiary">
        Folders appear in every deal, in this order. Drag a row to reorder them. Changes apply
        everywhere immediately.
      </p>

      <div className="rounded-md border border-border">
        <table className="w-full">
          <thead>
            <tr className="h-9 bg-surface-sunken text-left text-label text-text-tertiary">
              <th className="w-8 px-2" />
              <th className="px-4 font-medium">Name</th>
              <th className="w-10 px-2" />
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr className="h-10 border-t border-border">
                <td colSpan={3} className="px-4">
                  <div className="h-3 w-1/3 animate-pulse rounded bg-surface-sunken" />
                </td>
              </tr>
            )}
            {ordered.map((folder, index) => (
              <FolderRow
                key={folder.id}
                folder={folder}
                dragging={draggingIndex === index}
                onDragStart={() => startDrag(index)}
                onDragEnter={() => moveTo(index)}
                onDragEnd={commitOrder}
              />
            ))}
          </tbody>
        </table>
      </div>

      <AddFolderDialog open={addOpen} onOpenChange={setAddOpen} />
      </div>
    </>
  )
}
