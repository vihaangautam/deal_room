import { useRef, useState } from "react"
import { FileText, RotateCw, UploadCloud } from "lucide-react"
import { Dialog } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { useUpload, type UploadItem } from "@/hooks/useUpload"
import { formatBytes } from "@/lib/utils"
import type { Folder } from "@/api/types"

const STATUS_TEXT: Record<UploadItem["status"], (msg?: string) => string> = {
  hashing: () => "Preparing…",
  uploading: () => "Uploading",
  pending_approval: () => "Waiting for approval",
  active: () => "Added",
  duplicate: (msg) => msg ?? "Already uploaded",
  not_allowed: (msg) => msg ?? "Not allowed",
  failed: () => "Failed",
}

function Row({ item, onRetry }: { item: UploadItem; onRetry: () => void }) {
  const isError = item.status === "duplicate" || item.status === "not_allowed" || item.status === "failed"
  return (
    <div className="flex h-12 items-center gap-3 border-b border-border px-1 last:border-b-0">
      <FileText className="h-4 w-4 shrink-0 text-text-tertiary" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="truncate text-table font-medium text-text-primary">{item.file.name}</p>
        <div className="flex items-center gap-2">
          {item.status === "uploading" && (
            <div className="h-1 w-32 overflow-hidden rounded-full bg-[#EEF0EE]">
              <div
                className="h-full bg-brand-600 transition-all"
                style={{ width: `${item.progress}%` }}
              />
            </div>
          )}
          <p className={isError ? "text-meta text-text-warning" : "text-meta text-text-tertiary"}>
            {item.status === "uploading"
              ? `Uploading ${item.progress}%`
              : STATUS_TEXT[item.status](item.message)}
          </p>
        </div>
      </div>
      <span className="shrink-0 text-meta tabular-nums text-text-tertiary">
        {formatBytes(item.file.size)}
      </span>
      {item.status === "failed" && (
        <Button type="button" variant="ghost" size="sm" onClick={onRetry}>
          <RotateCw className="h-3.5 w-3.5" />
          Retry
        </Button>
      )}
    </div>
  )
}

export function MultiFileUploadDialog({
  open,
  onOpenChange,
  dealId,
  dealName,
  folders,
  defaultFolderId,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  dealId: string
  dealName: string
  folders: Folder[]
  defaultFolderId: string
}) {
  const [folderId, setFolderId] = useState(defaultFolderId)
  const { items, addFiles, retry, clear } = useUpload(dealId, folderId)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const uploadedCount = items.filter((i) => i.status === "active" || i.status === "pending_approval").length
  const stillUploading = items.some((i) => i.status === "uploading" || i.status === "hashing")

  function handleClose() {
    if (stillUploading) {
      if (!window.confirm("Uploads in progress will stop. Close anyway?")) return
    }
    clear()
    onOpenChange(false)
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => (v ? onOpenChange(v) : handleClose())}
      title={`Upload to ${dealName}`}
      width={640}
    >
      <div className="flex flex-col gap-4">
        <label className="flex flex-col gap-1.5">
          <span className="text-body-strong text-text-primary">Folder</span>
          <select
            value={folderId}
            onChange={(e) => setFolderId(e.target.value)}
            className="h-9 rounded-md border border-border bg-surface-sunken px-3 text-body text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-600"
          >
            {folders.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
        </label>

        <div
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            addFiles(Array.from(e.dataTransfer.files))
          }}
          className={`flex h-30 flex-col items-center justify-center gap-1 rounded-lg border border-dashed text-center ${
            dragging ? "border-brand-600 bg-brand-50" : "border-border-strong"
          }`}
          style={{ minHeight: 120 }}
        >
          <UploadCloud className="h-5 w-5 text-text-tertiary" aria-hidden />
          <p className="text-body text-text-primary">
            Drag files here or{" "}
            <button
              type="button"
              className="text-brand-700 underline"
              onClick={() => fileInputRef.current?.click()}
            >
              Choose files
            </button>
          </p>
          <p className="text-meta text-text-tertiary">PDF, Word, Excel or CSV. Up to 2 GB each.</p>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => {
              if (e.target.files) addFiles(Array.from(e.target.files))
              e.target.value = ""
            }}
          />
        </div>

        {items.length > 0 && (
          <div className="max-h-80 overflow-y-auto rounded-md border border-border">
            {items.map((item) => (
              <Row key={item.id} item={item} onRetry={() => retry(item.id)} />
            ))}
          </div>
        )}

        <div className="flex items-center justify-between">
          <span className="text-meta text-text-tertiary">
            {items.length > 0 ? `${uploadedCount} of ${items.length} uploaded` : ""}
          </span>
          <Button type="button" variant="secondary" onClick={handleClose}>
            Close
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
