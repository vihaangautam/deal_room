import { useCallback, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { apiFetch, ApiError } from "@/api/client"

// CLAUDE.md §6.5. CHUNK_SIZE matches the backend's MAX_CHUNK_SIZE
// (app/routers/upload.py) — chunks exist to avoid one huge request body
// through the Cloudflare Tunnel, not real S3 multipart upload.
const CHUNK_SIZE = 32 * 1024 * 1024

export type UploadItemStatus =
  | "hashing"
  | "uploading"
  | "pending_approval"
  | "active"
  | "duplicate"
  | "failed"
  | "not_allowed"

export interface UploadItem {
  id: string
  file: File
  status: UploadItemStatus
  progress: number // 0-100
  message?: string
}

const ALLOWED_EXTENSIONS = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv"]

async function sha256Hex(file: File): Promise<string> {
  const buffer = await file.arrayBuffer()
  const hashBuffer = await crypto.subtle.digest("SHA-256", buffer)
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
}

export function useUpload(dealId: string, folderId: string) {
  const [items, setItems] = useState<UploadItem[]>([])
  const qc = useQueryClient()

  const update = useCallback((id: string, patch: Partial<UploadItem>) => {
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, ...patch } : it)))
  }, [])

  const uploadOne = useCallback(
    async (id: string, file: File) => {
      const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase()
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        update(id, { status: "not_allowed", message: `Not allowed: ${ext} files can't be uploaded.` })
        return
      }

      try {
        update(id, { status: "hashing" })
        const sha256 = await sha256Hex(file)

        const init = await apiFetch<{ doc_id: string }>(`/deals/${dealId}/documents/init`, {
          method: "POST",
          body: { filename: file.name, size: file.size, sha256, mime_type: file.type, folder_id: folderId },
        })
        const docId = init.doc_id

        const totalChunks = Math.max(1, Math.ceil(file.size / CHUNK_SIZE))
        update(id, { status: "uploading", progress: 0 })
        for (let i = 0; i < totalChunks; i += 1) {
          const chunk = file.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE)
          const form = new FormData()
          form.append("chunk_index", String(i))
          form.append("total_chunks", String(totalChunks))
          form.append("data", chunk, file.name)
          await apiFetch(`/upload/${docId}/chunk`, { method: "POST", body: form })
          update(id, { progress: Math.round(((i + 1) / totalChunks) * 100) })
        }

        const complete = await apiFetch<{ status: string }>(`/upload/${docId}/complete`, {
          method: "POST",
        })
        update(id, {
          status: complete.status === "active" ? "active" : "pending_approval",
          progress: 100,
        })
        qc.invalidateQueries({ queryKey: ["documents", dealId] })
        qc.invalidateQueries({ queryKey: ["approvals"] })
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          update(id, { status: "duplicate", message: String(err.detail) })
        } else if (err instanceof ApiError && err.status === 422) {
          update(id, { status: "not_allowed", message: String(err.detail) })
        } else {
          update(id, { status: "failed", message: "Upload failed." })
        }
      }
    },
    [dealId, folderId, update, qc],
  )

  const addFiles = useCallback(
    (files: File[]) => {
      // DESIGN.md §5.5: uploads start automatically when files are added.
      const newItems: UploadItem[] = files.map((file) => ({
        id: crypto.randomUUID(),
        file,
        status: "hashing",
        progress: 0,
      }))
      setItems((prev) => [...prev, ...newItems])
      newItems.forEach((item) => {
        void uploadOne(item.id, item.file)
      })
    },
    [uploadOne],
  )

  const retry = useCallback(
    (id: string) => {
      const item = items.find((it) => it.id === id)
      if (item) void uploadOne(id, item.file)
    },
    [items, uploadOne],
  )

  const clear = useCallback(() => setItems([]), [])

  return { items, addFiles, retry, clear }
}
