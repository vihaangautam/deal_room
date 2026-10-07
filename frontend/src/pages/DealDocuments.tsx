import { useMemo, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { FileSpreadsheet, FileText, Lock, Upload } from "lucide-react"
import { useDeal } from "@/api/deals"
import { useDocuments, useRenameDocument, useRequestDeleteDocument, documentDownloadUrl } from "@/api/documents"
import { useFolders } from "@/api/folders"
import { useMyPermissions } from "@/api/permissions"
import { useAuthStore } from "@/stores/auth"
import { DealHeader } from "@/components/DealHeader"
import { DocumentStatusPill } from "@/components/StatusPill"
import { Button } from "@/components/ui/button"
import { toast } from "@/components/ui/toast"
import { Dialog, DialogFooter } from "@/components/ui/dialog"
import { RowMenu, RowMenuItem } from "@/components/ui/dropdown-menu"
import { MultiFileUploadDialog } from "@/components/MultiFileUpload"
import { StageChangeDialog } from "@/components/StageChangeDialog"
import { cn, formatBytes, formatDate } from "@/lib/utils"
import type { AccessLevel, DocumentItem } from "@/api/types"

function FileIcon({ mimeType }: { mimeType: string }) {
  if (mimeType.includes("spreadsheet") || mimeType.includes("csv") || mimeType.includes("excel")) {
    return <FileSpreadsheet className="h-4 w-4 text-text-tertiary" aria-hidden />
  }
  return <FileText className="h-4 w-4 text-text-tertiary" aria-hidden />
}

function DeleteRequestDialog({
  open,
  onOpenChange,
  doc,
  onConfirm,
  pending,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  doc: DocumentItem | null
  onConfirm: (reason: string) => void
  pending: boolean
}) {
  const [reason, setReason] = useState("")
  if (!doc) return null
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={`Request deletion of '${doc.display_name}'?`} width={440}>
      <p className="text-body text-text-secondary">
        Samir will review this. If approved, the file moves to the Archive and stops appearing here.
      </p>
      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Reason (optional)"
        className="mt-3 h-20 w-full rounded-md border border-border bg-surface-sunken p-2 text-body text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-600"
      />
      <DialogFooter>
        <Button variant="secondary" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button loading={pending} onClick={() => onConfirm(reason)}>
          Request deletion
        </Button>
      </DialogFooter>
    </Dialog>
  )
}

function FileRow({
  doc,
  dealId,
  access,
  dealClosed,
}: {
  doc: DocumentItem
  dealId: string
  access: AccessLevel
  dealClosed: boolean
}) {
  const user = useAuthStore((s) => s.user)
  const rename = useRenameDocument(dealId)
  const requestDelete = useRequestDeleteDocument(dealId)
  const [renaming, setRenaming] = useState(false)
  const [baseName, setBaseName] = useState(() => doc.display_name.replace(/\.[^.]+$/, ""))
  const [deleteOpen, setDeleteOpen] = useState(false)
  const ext = doc.display_name.slice(doc.display_name.lastIndexOf("."))

  const isOwnPending = doc.status === "pending" && doc.uploaded_by_name === user?.display_name
  const isOwnRejected = doc.status === "rejected"
  const isLinkable = doc.status === "active" || doc.status === "delete_requested"
  // PRD F3: rename and delete request are disabled on a closed deal.
  const canContribute = access === "contribute" && !dealClosed

  function saveRename() {
    const next = baseName.trim()
    setRenaming(false)
    if (!next || `${next}${ext}` === doc.display_name) return

    // DESIGN.md §5.12 names rename as the case that must carry Undo. The
    // old base name is only in hand here, which is why this toast is
    // raised at the call site rather than in the mutation hook.
    const previous = doc.display_name.replace(/\.[^.]+$/, "")
    rename.mutate(
      { docId: doc.id, baseName: next },
      {
        onSuccess: () =>
          toast(`Renamed to '${next}${ext}'.`, {
            undo: () => {
              setBaseName(previous)
              rename.mutate({ docId: doc.id, baseName: previous })
            },
          }),
      },
    )
  }

  return (
    <tr className="group h-10 border-t border-border hover:bg-surface-hover">
      <td className="px-4">
        <div className="flex items-center gap-2">
          <FileIcon mimeType={doc.mime_type} />
          {renaming ? (
            <input
              autoFocus
              value={baseName}
              onChange={(e) => setBaseName(e.target.value)}
              onBlur={saveRename}
              onKeyDown={(e) => {
                if (e.key === "Enter") saveRename()
                if (e.key === "Escape") setRenaming(false)
              }}
              className="h-8 w-48 rounded border border-border-strong bg-surface px-2 text-table"
            />
          ) : isLinkable ? (
            <a
              href={documentDownloadUrl(dealId, doc.id)}
              className={cn(
                "text-table font-medium text-text-primary hover:underline",
              )}
            >
              {doc.display_name}
            </a>
          ) : (
            <span
              className="text-table font-medium text-text-tertiary"
              title={
                isOwnPending
                  ? "Samir needs to approve this file before others can see it."
                  : undefined
              }
            >
              {doc.display_name}
            </span>
          )}
          {renaming && <span className="text-table text-text-tertiary">{ext}</span>}
        </div>
        {isOwnRejected && (
          <p className="mt-0.5 pl-6 text-meta text-text-danger">Rejected</p>
        )}
      </td>
      <td className="px-4 text-right tabular-nums text-table text-text-secondary">
        {formatBytes(doc.size_bytes)}
      </td>
      <td className="px-4 text-table text-text-secondary">{doc.uploaded_by_name}</td>
      <td className="px-4 text-right tabular-nums text-table text-text-secondary">
        {formatDate(doc.created_at)}
      </td>
      <td className="px-4">
        <DocumentStatusPill status={doc.status} />
      </td>
      <td className="w-10 px-2">
        {doc.status === "active" && canContribute && (
          <RowMenu>
            <RowMenuItem onSelect={() => setRenaming(true)}>Rename</RowMenuItem>
            <RowMenuItem danger onSelect={() => setDeleteOpen(true)}>
              Request deletion
            </RowMenuItem>
          </RowMenu>
        )}
      </td>

      <DeleteRequestDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        doc={doc}
        pending={requestDelete.isPending}
        onConfirm={(reason) => {
          requestDelete.mutate(
            { docId: doc.id, reason: reason || undefined },
            {
              // An approver's own request archives at once (PRD §7), so
              // the two outcomes need different words.
              onSuccess: (result) =>
                toast(
                  result.status === "archived"
                    ? `'${doc.display_name}' moved to the Archive.`
                    : `Deletion requested. Samir will review it.`,
                ),
            },
          )
          setDeleteOpen(false)
        }}
      />
    </tr>
  )
}

export function DealDocuments() {
  const { dealId, folderId } = useParams<{ dealId: string; folderId?: string }>()
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const { data: deal } = useDeal(dealId)
  const { data: folders } = useFolders()
  const { data: documents, isLoading } = useDocuments(dealId)
  const { data: myPermissions } = useMyPermissions()
  const [uploadOpen, setUploadOpen] = useState(false)
  const [stageDialogOpen, setStageDialogOpen] = useState(false)

  const selectedFolderId = folderId ?? folders?.[0]?.id

  const folderDocCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const doc of documents ?? []) {
      if (doc.status !== "active") continue
      counts.set(doc.folder_id, (counts.get(doc.folder_id) ?? 0) + 1)
    }
    return counts
  }, [documents])

  const visibleDocs = useMemo(
    () => (documents ?? []).filter((d) => d.folder_id === selectedFolderId),
    [documents, selectedFolderId],
  )

  const selectedFolder = folders?.find((f) => f.id === selectedFolderId)
  const selectedAccess: AccessLevel = (selectedFolderId && myPermissions?.[selectedFolderId]) || "none"
  const canContributeAnywhere = Object.values(myPermissions ?? {}).includes("contribute")
  const dealClosed = deal?.stage === "successful" || deal?.stage === "dropped"

  if (!dealId || !deal) return null

  return (
    <div className="px-6 py-6">
      <DealHeader
        deal={deal}
        actions={
          <>
            {user?.role === "admin" && (
              <Button variant="secondary" onClick={() => setStageDialogOpen(true)}>
                Change stage
              </Button>
            )}
            {canContributeAnywhere && (!dealClosed || deal.allow_uploads_when_closed) && (
              <Button onClick={() => setUploadOpen(true)}>
                <Upload className="h-4 w-4" />
                Upload files
              </Button>
            )}
          </>
        }
      />

      {dealClosed && (
        <div className="mb-4 rounded-md bg-info-50 px-3 py-2 text-body text-text-info">
          This deal is closed. Files can be downloaded but not changed.
        </div>
      )}

      <div className="flex gap-6">
        <div className="w-[260px] shrink-0 rounded-md border border-border">
          {folders?.map((folder) => {
            const access = myPermissions?.[folder.id] ?? "none"
            const locked = access === "none"
            const active = folder.id === selectedFolderId
            return (
              <button
                key={folder.id}
                type="button"
                disabled={locked}
                onClick={() => navigate(`/deals/${dealId}/documents/${folder.id}`)}
                title={locked ? "You don't have access to this folder. Ask Samir." : undefined}
                className={cn(
                  "flex h-9 w-full items-center gap-2 border-b border-border px-3 text-left last:border-b-0",
                  active ? "bg-brand-50 text-brand-700" : "text-text-primary hover:bg-surface-hover",
                  locked && "cursor-not-allowed",
                )}
              >
                <span className={cn("flex-1 truncate text-body-strong", locked && "text-text-tertiary")}>
                  {folder.name}
                </span>
                {locked ? (
                  <Lock className="h-4 w-4 shrink-0 text-text-tertiary" aria-hidden />
                ) : (
                  <span className="text-meta text-text-tertiary">
                    {folderDocCounts.get(folder.id) ?? 0}
                  </span>
                )}
              </button>
            )
          })}
        </div>

        <div className="flex-1 rounded-md border border-border">
          <div className="flex h-11 items-center gap-2 border-b border-border px-4">
            <span className="text-title-section text-text-primary">{selectedFolder?.name}</span>
            <span className="text-table text-text-tertiary">{visibleDocs.length} files</span>
          </div>

          {selectedAccess === "none" ? (
            <div className="px-4 py-10 text-center">
              <p className="text-body-strong text-text-primary">
                You don't have access to {selectedFolder?.name}
              </p>
              <p className="text-table text-text-secondary">Ask Samir if you need to see these files.</p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="h-9 bg-surface-sunken text-left text-label text-text-tertiary">
                  <th className="px-4 font-medium">Name</th>
                  <th className="px-4 text-right font-medium">Size</th>
                  <th className="px-4 font-medium">Uploaded by</th>
                  <th className="px-4 text-right font-medium">Uploaded on</th>
                  <th className="px-4 font-medium">Status</th>
                  <th className="w-10 px-2" />
                </tr>
              </thead>
              <tbody>
                {isLoading &&
                  [0, 1, 2].map((i) => (
                    <tr key={i} className="h-10 border-t border-border">
                      <td colSpan={6} className="px-4">
                        <div className="h-3 w-1/3 animate-pulse rounded bg-surface-sunken" />
                      </td>
                    </tr>
                  ))}
                {!isLoading && visibleDocs.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-10 text-center">
                      <p className="text-body-strong text-text-primary">
                        No files in {selectedFolder?.name}
                      </p>
                      <p className="text-table text-text-secondary">
                        Upload files for this deal in this folder.
                      </p>
                    </td>
                  </tr>
                )}
                {visibleDocs.map((doc) => (
                  <FileRow
                    key={doc.id}
                    doc={doc}
                    dealId={dealId}
                    access={selectedAccess}
                    dealClosed={dealClosed}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {folders && selectedFolderId && (
        <MultiFileUploadDialog
          open={uploadOpen}
          onOpenChange={setUploadOpen}
          dealId={dealId}
          dealName={deal.name}
          folders={folders.filter((f) => (myPermissions?.[f.id] ?? "none") === "contribute")}
          defaultFolderId={selectedFolderId}
        />
      )}

      <StageChangeDialog open={stageDialogOpen} onOpenChange={setStageDialogOpen} deal={deal} />
    </div>
  )
}
