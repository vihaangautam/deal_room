import type { ReactNode } from "react"
import { Link, useLocation } from "react-router-dom"
import { useComments } from "@/api/comments"
import { useDealActivity } from "@/api/deals"
import { useDocuments } from "@/api/documents"
import { useTasks } from "@/api/tasks"
import { useAuthStore } from "@/stores/auth"
import { DealStagePill } from "@/components/StatusPill"
import { PageHeader } from "@/components/PageHeader"
import { Tab, TabBand } from "@/components/TabBand"
import type { DealDetail } from "@/api/types"

// DESIGN.md §6.3: breadcrumb, title plus stage pill, actions on the right,
// then the tab bar "Documents 28 · Tasks 5 · Activity 42". One component
// for all three deal pages — DealTasks used to render a plain
// "Sharma Infra Ltd — Tasks" heading with no tabs, so there was no way
// back to the files except the browser's back button.
export function DealHeader({ deal, actions }: { deal: DealDetail; actions?: ReactNode }) {
  const location = useLocation()
  const user = useAuthStore((s) => s.user)
  const isAdmin = user?.role === "admin"

  const { data: documents } = useDocuments(deal.id)
  const { data: tasks } = useTasks(deal.stage === "running" ? deal.id : undefined)
  const { data: comments } = useComments(deal.id)
  const { data: activity } = useDealActivity(isAdmin ? deal.id : undefined)

  // Every document the viewer can see in this deal — the same rows the
  // folder list counts, so the tab and the folder list cannot disagree.
  const documentCount = (documents ?? []).length
  // What the viewer can actually open: everyone sees the comments, only
  // admin sees the history (PRD §7).
  const activityCount = (comments?.length ?? 0) + (activity?.length ?? 0)

  const tabs = [
    { to: `/deals/${deal.id}/documents`, label: "Documents", count: documentCount, show: true },
    {
      to: `/deals/${deal.id}/tasks`,
      label: "Tasks",
      count: tasks?.length ?? 0,
      // PRD F8: no tasks on New or Old deals, so no tab either.
      show: deal.stage === "running",
    },
    { to: `/deals/${deal.id}/activity`, label: "Activity", count: activityCount, show: true },
  ].filter((t) => t.show)

  return (
    <>
      <PageHeader
        breadcrumb={
          <Link to="/deals" className="hover:underline">
            Deals
          </Link>
        }
        title={deal.name}
        pill={<DealStagePill stage={deal.stage} />}
        actions={actions}
      />
      <TabBand
        tabs={tabs.map((tab) => (
          <Tab key={tab.to} active={location.pathname.startsWith(tab.to)} count={tab.count}>
            <Link to={tab.to} className="flex h-full items-center gap-1.5">
              {tab.label}
            </Link>
          </Tab>
        ))}
      />
    </>
  )
}
