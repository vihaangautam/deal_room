import { useParams } from "react-router-dom"
import { useDeal } from "@/api/deals"
import { CommentThread } from "@/components/CommentThread"
import { DealHeader } from "@/components/DealHeader"
import { PageBody } from "@/components/PageBody"

// Split out of the Activity tab. PRD §57 defines the two as opposites —
// "Activity is the automatic, append-only record of every action on a
// deal… a backward-looking record nobody writes by hand" — and comments
// are the only thing on that screen a human writes. PRD §7 then puts the
// permission line between them: everyone comments, only admin reads the
// history. One tab covering both meant a member saw a tab called Activity
// that contained nothing but comments, and a count that added two
// unrelated numbers together.
//
// The task page keeps its combined All · Comments · History (DESIGN
// §5.11). At that level the history is short and genuinely interleaves
// with the conversation; at deal level the two diverge by an order of
// magnitude.
export function DealComments() {
  const { dealId } = useParams<{ dealId: string }>()
  const { data: deal } = useDeal(dealId)

  if (!dealId || !deal) return null

  // PRD F3: a closed deal is read-only, commenting included.
  const dealClosed = deal.stage === "successful" || deal.stage === "dropped"

  return (
    <>
      <DealHeader deal={deal} />
      <PageBody>
        {/* Capped: a comment thread running the full width of a 1400px
            column is unreadable. */}
        <div className="max-w-[720px]">
          <CommentThread dealId={dealId} readOnly={dealClosed} />
        </div>
      </PageBody>
    </>
  )
}
