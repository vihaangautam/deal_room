import { useState } from "react"
import { Plus } from "lucide-react"
import { useCreateFolder, useDeleteFolder, useFolders, useRenameFolder, isFolderDeleteBlocked } from "@/api/folders"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Field } from "@/components/ui/field"
import { Dialog, DialogFooter } from "@/components/ui/dialog"
import { RowMenu, RowMenuItem } from "@/components/ui/dropdown-menu"
import type { Folder } from "@/api/types"

function AddFolderDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const createFolder = useCreateFolder()
  const [name, setName] = useState("")
  const [defaultAccess, setDefaultAccess] = useState<"none" | "view">("view")

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    await createFolder.mutateAsync({ name, default_access: defaultAccess })
    setName("")
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
          helper="You can change access per person afterwards in Users & permissions."
        >
          <div className="flex gap-4">
            <label className="flex items-center gap-1.5 text-body text-text-primary">
              <input
                type="radio"
                checked={defaultAccess === "view"}
                onChange={() => setDefaultAccess("view")}
              />
              View
            </label>
            <label className="flex items-center gap-1.5 text-body text-text-primary">
              <input
                type="radio"
                checked={defaultAccess === "none"}
                onChange={() => setDefaultAccess("none")}
              />
              None
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

function FolderRow({ folder }: { folder: Folder }) {
  const rename = useRenameFolder()
  const deleteFolder = useDeleteFolder()
  const [renaming, setRenaming] = useState(false)
  const [name, setName] = useState(folder.name)
  const [blockedMessage, setBlockedMessage] = useState<string | null>(null)

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
    <tr className="h-10 border-t border-border hover:bg-surface-hover">
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
          <RowMenuItem danger onSelect={handleDelete}>
            Delete
          </RowMenuItem>
        </RowMenu>
      </td>

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
  const [addOpen, setAddOpen] = useState(false)

  return (
    <div className="px-6 py-6">
      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-title-page text-text-primary">Folders</h1>
        <Button onClick={() => setAddOpen(true)}>
          <Plus className="h-4 w-4" />
          Add folder
        </Button>
      </div>
      <p className="mb-4 text-table text-text-tertiary">
        Folders appear in every deal. Changes apply everywhere immediately.
      </p>

      <div className="rounded-md border border-border">
        <table className="w-full">
          <thead>
            <tr className="h-9 bg-surface-sunken text-left text-label text-text-tertiary">
              <th className="px-4 font-medium">Name</th>
              <th className="w-10 px-2" />
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr className="h-10 border-t border-border">
                <td colSpan={2} className="px-4">
                  <div className="h-3 w-1/3 animate-pulse rounded bg-surface-sunken" />
                </td>
              </tr>
            )}
            {folders?.map((folder) => (
              <FolderRow key={folder.id} folder={folder} />
            ))}
          </tbody>
        </table>
      </div>

      <AddFolderDialog open={addOpen} onOpenChange={setAddOpen} />
    </div>
  )
}
