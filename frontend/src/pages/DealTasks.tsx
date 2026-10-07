import { useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { useCreateTask, useTasks } from "@/api/tasks"
import { useDeal } from "@/api/deals"
import { DealHeader } from "@/components/DealHeader"
import { TaskStatusPill, NeedsAttentionPill } from "@/components/StatusPill"
import { cn, formatDate } from "@/lib/utils"
import type { TaskListItem, TaskPriority } from "@/api/types"

const PRIORITY_COLOR: Record<TaskPriority, string> = {
  high: "bg-[#8A5A00]",
  medium: "bg-border-strong",
  low: "bg-border",
}

function isOverdue(task: TaskListItem): boolean {
  if (!task.due_date || task.status === "done") return false
  return new Date(task.due_date) < new Date(new Date().toDateString())
}

function TaskRow({ task, dealId }: { task: TaskListItem; dealId: string }) {
  const navigate = useNavigate()
  const overdue = isOverdue(task)
  return (
    <tr
      onClick={() => navigate(`/deals/${dealId}/tasks/${task.id}`)}
      className="h-10 cursor-pointer border-t border-border hover:bg-surface-hover"
    >
      <td className="px-4">
        <div className="flex items-center gap-2">
          <span className={cn("h-2 w-2 shrink-0 rounded-full", PRIORITY_COLOR[task.priority])} />
          <span className="text-meta text-text-tertiary">{task.key}</span>
          <span className="text-table font-medium text-text-primary">{task.title}</span>
        </div>
      </td>
      <td className="px-4">
        <div className="flex items-center gap-1.5">
          <TaskStatusPill status={task.status} />
          {task.needs_attention && <NeedsAttentionPill />}
        </div>
      </td>
      <td className="px-4 text-right tabular-nums text-table text-text-secondary">
        {task.due_date ? (
          <span className={overdue ? "text-text-danger" : undefined}>
            {formatDate(task.due_date)} {overdue && "· Overdue"}
          </span>
        ) : (
          "—"
        )}
      </td>
      <td className="px-4 text-table text-text-secondary">{task.assignee_name ?? "Unassigned"}</td>
      <td className="px-4 text-table text-text-secondary">{task.reporter_name}</td>
    </tr>
  )
}

export function DealTasks() {
  const { dealId } = useParams<{ dealId: string }>()
  const { data: deal } = useDeal(dealId)
  const { data: tasks, isLoading } = useTasks(dealId)
  const createTask = useCreateTask(dealId ?? "")
  const [creating, setCreating] = useState(false)
  const [title, setTitle] = useState("")

  if (!dealId || !deal) return null

  function submitCreate() {
    if (title.trim()) {
      createTask.mutate({ title: title.trim() })
      setTitle("")
    }
    setCreating(false)
  }

  return (
    <>
    <DealHeader deal={deal} />
      <div className="px-6 py-6">
      <div className="rounded-md border border-border">
        <table className="w-full">
          <thead>
            <tr className="h-9 bg-surface-sunken text-left text-label text-text-tertiary">
              <th className="px-4 font-medium">Task</th>
              <th className="px-4 font-medium">Status</th>
              <th className="px-4 text-right font-medium">Due</th>
              <th className="px-4 font-medium">Assignee</th>
              <th className="px-4 font-medium">Reporter</th>
            </tr>
          </thead>
          <tbody>
            {isLoading &&
              [0, 1].map((i) => (
                <tr key={i} className="h-10 border-t border-border">
                  <td colSpan={5} className="px-4">
                    <div className="h-3 w-1/3 animate-pulse rounded bg-surface-sunken" />
                  </td>
                </tr>
              ))}
            {!isLoading && (tasks?.length ?? 0) === 0 && !creating && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center">
                  <p className="text-body-strong text-text-primary">No tasks yet</p>
                  <p className="text-table text-text-secondary">
                    Create a task to hand off work on this deal.
                  </p>
                </td>
              </tr>
            )}
            {tasks?.map((task) => (
              <TaskRow key={task.id} task={task} dealId={dealId} />
            ))}
            <tr className="h-10 border-t border-border bg-surface-sunken">
              <td colSpan={5} className="px-4">
                {creating ? (
                  <input
                    autoFocus
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    onBlur={submitCreate}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") submitCreate()
                      if (e.key === "Escape") setCreating(false)
                    }}
                    placeholder="What needs doing?"
                    className="h-7 w-full max-w-md rounded border border-border-strong bg-surface px-2 text-table focus:outline-none"
                  />
                ) : (
                  <button
                    type="button"
                    onClick={() => setCreating(true)}
                    className="text-body-strong text-text-secondary hover:text-text-primary"
                  >
                    + Create task
                  </button>
                )}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      </div>
    </>
  )
}
