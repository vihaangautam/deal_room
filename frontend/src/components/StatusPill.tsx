import { cn } from "@/lib/utils"

// DESIGN.md §3.1's status table — one shared component for every status
// value across deals/documents/tasks, since they share the same five
// semantic colors (plus the one-off "dropped" muted brown).
const PILL_STYLES = {
  neutral: "bg-pill-neutral-bg text-pill-neutral-text",
  info: "bg-pill-info-bg text-pill-info-text",
  success: "bg-pill-success-bg text-pill-success-text",
  warning: "bg-pill-warning-bg text-pill-warning-text",
  danger: "bg-pill-danger-bg text-pill-danger-text",
  dropped: "bg-pill-dropped-bg text-pill-dropped-text",
} as const

type PillTone = keyof typeof PILL_STYLES

const DEAL_STAGE_TONE: Record<string, PillTone> = {
  new: "neutral",
  running: "info",
  successful: "success",
  dropped: "dropped",
}

const DOCUMENT_STATUS_TONE: Record<string, PillTone> = {
  uploading: "warning",
  pending: "warning",
  delete_requested: "warning",
  rejected: "danger",
  archived: "neutral",
  // 'active' renders no pill at all — see DocumentStatusPill below.
}

const TASK_STATUS_TONE: Record<string, PillTone> = {
  not_started: "neutral",
  in_progress: "info",
  submitted: "warning",
  done: "success",
}

export const DEAL_STAGE_LABEL: Record<string, string> = {
  new: "New",
  running: "Running",
  successful: "Successful",
  dropped: "Dropped",
}

const DOCUMENT_STATUS_LABEL: Record<string, string> = {
  uploading: "Uploading…",
  pending: "Pending approval",
  delete_requested: "Deletion requested",
  rejected: "Rejected",
  archived: "Archived",
}

const TASK_STATUS_LABEL: Record<string, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  submitted: "Awaiting approval",
  done: "Done",
}

function Pill({ tone, children }: { tone: PillTone; children: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center gap-1.5 rounded-full px-2 text-pill",
        PILL_STYLES[tone],
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {children}
    </span>
  )
}

export function DealStagePill({ stage }: { stage: string }) {
  return <Pill tone={DEAL_STAGE_TONE[stage] ?? "neutral"}>{DEAL_STAGE_LABEL[stage] ?? stage}</Pill>
}

export function DocumentStatusPill({ status }: { status: string }) {
  // Active is the normal state — no pill on a row is noise (DESIGN.md §3.1).
  if (status === "active") return null
  return (
    <Pill tone={DOCUMENT_STATUS_TONE[status] ?? "neutral"}>
      {DOCUMENT_STATUS_LABEL[status] ?? status}
    </Pill>
  )
}

export function TaskStatusPill({ status }: { status: string }) {
  return <Pill tone={TASK_STATUS_TONE[status] ?? "neutral"}>{TASK_STATUS_LABEL[status] ?? status}</Pill>
}

export function NeedsAttentionPill() {
  return <Pill tone="danger">Needs attention</Pill>
}
