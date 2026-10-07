// Mirrors the Pydantic response schemas in backend/app/schemas/.

export interface User {
  id: string
  email: string
  display_name: string
  role: "admin" | "member"
  can_approve: boolean
  must_change_password: boolean
}

export type DealStage = "new" | "running" | "successful" | "dropped"

export interface DealListItem {
  id: string
  name: string
  short_code: string
  borrower: string
  stage: DealStage
  created_at: string
  updated_at: string
  document_count: number
  tasks_done: number
  tasks_total: number
}

export interface DealDetail {
  id: string
  name: string
  short_code: string
  borrower: string
  summary: string
  stage: DealStage
  amount_cr: string | null
  allow_uploads_when_closed: boolean
  created_at: string
  updated_at: string
}

export interface DealStageHistoryItem {
  from_stage: DealStage | null
  to_stage: DealStage
  reason: string
  changed_at: string
}

export interface Folder {
  id: string
  name: string
  display_order: number
  /** Files across every deal, counting the statuses that block deletion. */
  file_count: number
  created_at: string | null
}

export type AccessLevel = "none" | "view" | "contribute"

export type DocumentStatus =
  | "uploading"
  | "pending"
  | "active"
  | "delete_requested"
  | "archived"
  | "rejected"

export interface DocumentItem {
  id: string
  folder_id: string
  display_name: string
  size_bytes: number
  mime_type: string
  status: DocumentStatus
  uploaded_by_name: string
  created_at: string
}

export type TaskStatus = "not_started" | "in_progress" | "submitted" | "done"
export type TaskPriority = "low" | "medium" | "high"

export interface TaskListItem {
  id: string
  key: string
  title: string
  status: TaskStatus
  needs_attention: boolean
  priority: TaskPriority
  assignee_name: string | null
  reporter_name: string
  due_date: string | null
  deal_id: string
  deal_name?: string
  updated_at: string
}

export interface TaskDetail {
  id: string
  key: string
  deal_id: string
  title: string
  description: string | null
  status: TaskStatus
  needs_attention: boolean
  priority: TaskPriority
  assignee_id: string | null
  assignee_name: string | null
  reporter_id: string
  reporter_name: string
  assigned_by_id: string | null
  assigned_by_name: string | null
  start_date: string | null
  due_date: string | null
  created_at: string
  updated_at: string
  pending_reassignment_to: string | null
  attachments: TaskAttachmentItem[]
}

export interface TaskAttachmentItem {
  document_id: string
  restricted: boolean
  display_name: string | null
  folder_name: string | null
  status: DocumentStatus | null
}

export interface Comment {
  id: string
  parent_id: string | null
  author_id: string
  author_name: string
  body: string
  edited: boolean
  deleted: boolean
  created_at: string
}

export type ApprovalType = "document_upload" | "document_delete" | "task_reassign" | "task_delete"

export interface ApprovalItem {
  id: string
  type: ApprovalType
  deal_id: string
  deal_name: string
  item_label: string
  item_sublabel: string | null
  requested_by_name: string
  requested_at: string
  note: string | null
}

export interface BulkActionResult {
  approved: number
  rejected: number
  already_handled: number
  errors: string[]
}

export interface UserAdmin {
  id: string
  display_name: string
  email: string
  role: "admin" | "member"
  can_approve: boolean
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

export interface PermissionMatrixEntry {
  user_id: string
  user_name: string
  folder_id: string
  folder_name: string
  access_level: AccessLevel
}

export interface ArchiveItem {
  id: string
  display_name: string
  deal_id: string
  deal_name: string
  folder_name: string
  deleted_by_name: string | null
  approved_by_name: string | null
  deleted_at: string
  reason: string | null
}

export interface AuditLogItem {
  id: number
  actor_id: string | null
  actor_name: string | null
  action: string
  entity_type: string
  entity_id: string
  detail: unknown
  deal_id: string | null
  deal_name: string | null
  created_at: string
}
