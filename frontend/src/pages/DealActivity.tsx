import { Navigate, useParams } from "react-router-dom"
import { useDeal, useDealActivity } from "@/api/deals"
import { useAuthStore } from "@/stores/auth"
import { ActivityFeed } from "@/components/ActivityFeed"
import { DealHeader } from "@/components/DealHeader"
import { PageBody } from "@/components/PageBody"

// Just the history now; the comment thread moved to its own tab (see
// DealComments). PRD §7's permission matrix gives "View Archive /
// Activity" to admin alone, so this whole page is admin-only and the tab
// is hidden from everyone else rather than shown empty.
export function DealActivity() {
  const { dealId } = useParams<{ dealId: string }>()
  const user = useAuthStore((s) => s.user)
  const isAdmin = user?.role === "admin"
  const { data: deal } = useDeal(dealId)
  const { data: activity, isLoading } = useDealActivity(isAdmin ? dealId : undefined)

  if (!dealId) return null

  // A member reaching this by URL gets the tab they can actually use,
  // rather than a page that renders nothing and looks broken.
  if (user && !isAdmin) return <Navigate to={`/deals/${dealId}/comments`} replace />

  if (!deal) return null

  return (
    <>
      <DealHeader deal={deal} />
      <PageBody>
        <div className="overflow-hidden rounded-lg border border-border bg-surface">
          <ActivityFeed
            items={activity}
            isLoading={isLoading}
            emptyTitle="No activity yet"
            emptyBody="Actions on this deal will be recorded here."
          />
        </div>
      </PageBody>
    </>
  )
}
