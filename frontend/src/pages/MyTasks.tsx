import { useNavigate } from "react-router-dom"
import { useMyTasks } from "@/api/tasks"
import { TaskStatusPill, NeedsAttentionPill } from "@/components/StatusPill"
import { formatDate } from "@/lib/utils"
import type { TaskListItem, TaskStatus } from "@/api/types"

// DESIGN.md §6.6 — this exact order.
const GROUP_ORDER: TaskStatus[] = ["submitted", "in_progress", "not_started", "done"]
const GROUP_LABEL: Record<TaskStatus, string> = {
  submitted: "Awaiting approval",
  in_progress: "In progress",
  not_started: "Not started",
  done: "Done",
}

function isOverdue(task: TaskListItem): boolean {
  if (!task.due_date || task.status === "done") return false
  return new Date(task.due_date) < new Date(new Date().toDateString())
}

export function MyTasks() {
  const navigate = useNavigate()
  const { data: tasks, isLoading } = useMyTasks()

  if (isLoading) return null

  if (!tasks || tasks.length === 0) {
    return (
      <div className="px-6 py-6">
        <h1 className="mb-4 text-title-page text-text-primary">My Tasks</h1>
        <div className="rounded-md border border-border px-4 py-10 text-center">
          <p className="text-body-strong text-text-primary">Nothing assigned to you</p>
          <p className="text-table text-text-secondary">
            Tasks assigned to you on running deals appear here.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="px-6 py-6">
      <h1 className="mb-4 text-title-page text-text-primary">My Tasks</h1>

      <div className="flex flex-col gap-6">
        {GROUP_ORDER.map((status) => {
          const group = tasks
            .filter((t) => t.status === status)
            .sort((a, b) => {
              if (!a.due_date) return 1
              if (!b.due_date) return -1
              return new Date(a.due_date).getTime() - new Date(b.due_date).getTime()
            })
          if (group.length === 0) return null

          return (
            <section key={status}>
              <div className="mb-1 flex h-8 items-center gap-2 rounded-md bg-surface-sunken px-3">
                <span className="text-label text-text-tertiary">{GROUP_LABEL[status]}</span>
                <span className="text-meta text-text-tertiary">{group.length}</span>
              </div>
              <div className="rounded-md border border-border">
                {group.map((task) => {
                  const overdue = isOverdue(task)
                  return (
                    <button
                      key={task.id}
                      type="button"
                      onClick={() => navigate(`/deals/${task.deal_id}/tasks/${task.id}`)}
                      className="flex h-10 w-full items-center gap-3 border-b border-border px-4 text-left last:border-b-0 hover:bg-surface-hover"
                    >
                      <span className="w-20 shrink-0 text-meta text-text-tertiary">{task.key}</span>
                      <span className="flex-1 truncate text-table font-medium text-text-primary">
                        {task.title}
                      </span>
                      <span className="w-40 shrink-0 truncate text-table text-text-tertiary">
                        {task.deal_name}
                      </span>
                      {task.needs_attention && <NeedsAttentionPill />}
                      <TaskStatusPill status={task.status} />
                      <span
                        className={`w-28 shrink-0 text-right tabular-nums text-table ${overdue ? "text-text-danger" : "text-text-secondary"}`}
                      >
                        {task.due_date ? formatDate(task.due_date) : "—"}
                        {overdue && " · Overdue"}
                      </span>
                    </button>
                  )
                })}
              </div>
            </section>
          )
        })}
      </div>
    </div>
  )
}
