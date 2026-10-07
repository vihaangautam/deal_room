import { useState } from "react"
import { useChangeStage, useDealStageHistory } from "@/api/deals"
import { ApiError } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Dialog, DialogFooter } from "@/components/ui/dialog"
import { DealStagePill } from "@/components/StatusPill"
import { cn } from "@/lib/utils"
import type { DealDetail, DealStage } from "@/api/types"

// PRD §8's state machine, in DESIGN.md §5.10's card copy. 'dropped' isn't
// a free choice here — see the reopen branch in StageChangeDialog below,
// which computes the single allowed target from stage history instead.
const TRANSITIONS: Record<string, { stage: DealStage; label: string; consequence: string }[]> = {
  new: [
    { stage: "running", label: "Running", consequence: "Work has started. Tasks become available." },
    {
      stage: "dropped",
      label: "Dropped",
      consequence: "Deal will not proceed. Documents become read-only. You can reopen it later.",
    },
  ],
  running: [
    {
      stage: "successful",
      label: "Successful",
      consequence: "Deal closed successfully. Documents become read-only.",
    },
    {
      stage: "dropped",
      label: "Dropped",
      consequence: "Deal will not proceed. Documents become read-only. You can reopen it later.",
    },
  ],
  successful: [],
}

export function StageChangeDialog({
  open,
  onOpenChange,
  deal,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  deal: DealDetail
}) {
  const changeStage = useChangeStage(deal.id)
  const { data: history } = useDealStageHistory(deal.id)
  const [selected, setSelected] = useState<DealStage | null>(null)
  const [reason, setReason] = useState("")
  const [error, setError] = useState<string | null>(null)

  const isReopen = deal.stage === "dropped"
  const reopenTarget = isReopen ? history?.[0]?.from_stage ?? null : null
  const options = isReopen
    ? reopenTarget
      ? [
          {
            stage: reopenTarget,
            label: reopenTarget === "new" ? "New" : "Running",
            consequence: `Reopens the deal back to ${reopenTarget === "new" ? "New" : "Running"}.`,
          },
        ]
      : []
    : (TRANSITIONS[deal.stage] ?? [])

  async function handleSubmit() {
    if (!selected) return
    setError(null)
    try {
      await changeStage.mutateAsync({ to_stage: selected, reason })
      onOpenChange(false)
      setSelected(null)
      setReason("")
    } catch (err) {
      setError(
        err instanceof ApiError && typeof err.detail === "string"
          ? err.detail
          : "Couldn't change the stage. Check the reason and try again.",
      )
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={`Change stage — ${deal.name}`} width={480}>
      <div className="mb-4 flex items-center gap-2">
        <DealStagePill stage={deal.stage} />
        <span className="text-text-tertiary">→</span>
      </div>

      {error && <p className="mb-3 text-body text-text-danger">{error}</p>}

      <div className="flex flex-col gap-2">
        {options.map((opt) => (
          <button
            key={opt.stage}
            type="button"
            onClick={() => setSelected(opt.stage)}
            className={cn(
              "flex h-14 flex-col justify-center rounded-md border px-3 text-left",
              selected === opt.stage ? "border-brand-600 bg-brand-50" : "border-border hover:bg-surface-hover",
            )}
          >
            <span className="text-body-strong text-text-primary">{opt.label}</span>
            <span className="text-meta text-text-tertiary">{opt.consequence}</span>
          </button>
        ))}
        {options.length === 0 && (
          <p className="text-body text-text-tertiary">No transitions are available from this stage.</p>
        )}
      </div>

      <label className="mt-4 flex flex-col gap-1.5">
        <span className="text-body-strong text-text-primary">Reason</span>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="h-20 rounded-md border border-border bg-surface-sunken p-2 text-body focus:outline-none focus:ring-2 focus:ring-brand-600"
        />
        <span className="text-meta text-text-tertiary">Recorded in the deal history.</span>
      </label>

      <DialogFooter>
        <Button variant="secondary" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button
          disabled={!selected || reason.trim().length < 5}
          loading={changeStage.isPending}
          onClick={handleSubmit}
        >
          Change stage
        </Button>
      </DialogFooter>
    </Dialog>
  )
}
