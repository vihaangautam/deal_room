import { useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Plus, Search } from "lucide-react"
import { useCreateDeal, useDeals } from "@/api/deals"
import { ApiError } from "@/api/client"
import { useAuthStore } from "@/stores/auth"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Field } from "@/components/ui/field"
import { Dialog, DialogFooter } from "@/components/ui/dialog"
import { DealStagePill } from "@/components/StatusPill"
import { cn, formatDate } from "@/lib/utils"
import type { DealListItem } from "@/api/types"

type HomeTab = "new" | "running" | "old"
type OldFilter = "all" | "successful" | "dropped"

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diffMs / 60_000)
  if (minutes < 1) return "just now"
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days === 1 ? "" : "s"} ago`
}

function NewDealDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const navigate = useNavigate()
  const createDeal = useCreateDeal()
  const [name, setName] = useState("")
  const [shortCode, setShortCode] = useState("")
  const [borrower, setBorrower] = useState("")
  const [summary, setSummary] = useState("")
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      const deal = await createDeal.mutateAsync({ name, short_code: shortCode, borrower, summary })
      onOpenChange(false)
      navigate(`/deals/${deal.id}/documents`)
    } catch (err) {
      setError(
        err instanceof ApiError && typeof err.detail === "string"
          ? err.detail
          : "Couldn't create the deal. Check the fields and try again.",
      )
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="New deal" width={480}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && <p className="text-body text-text-danger">{error}</p>}
        <Field label="Deal name" htmlFor="name">
          <Input id="name" required value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Short code" htmlFor="code" helper="2-6 letters, e.g. KRSN.">
          <Input
            id="code"
            required
            maxLength={6}
            value={shortCode}
            onChange={(e) => setShortCode(e.target.value.toUpperCase())}
          />
        </Field>
        <Field label="Borrower" htmlFor="borrower">
          <Input id="borrower" required value={borrower} onChange={(e) => setBorrower(e.target.value)} />
        </Field>
        <Field label="Summary" htmlFor="summary" helper="One line, up to 280 characters.">
          <Input id="summary" required maxLength={280} value={summary} onChange={(e) => setSummary(e.target.value)} />
        </Field>
        <DialogFooter>
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" loading={createDeal.isPending}>
            Create deal
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  )
}

export function DealsHome() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const { data: deals, isLoading } = useDeals()
  const [tab, setTab] = useState<HomeTab>("running")
  const [oldFilter, setOldFilter] = useState<OldFilter>("all")
  const [search, setSearch] = useState("")
  const [dialogOpen, setDialogOpen] = useState(false)

  const counts = useMemo(() => {
    const list = deals ?? []
    return {
      new: list.filter((d) => d.stage === "new").length,
      running: list.filter((d) => d.stage === "running").length,
      old: list.filter((d) => d.stage === "successful" || d.stage === "dropped").length,
    }
  }, [deals])

  const rows = useMemo(() => {
    const list = deals ?? []
    const byTab = list.filter((d) => {
      if (tab === "new") return d.stage === "new"
      if (tab === "running") return d.stage === "running"
      if (oldFilter === "successful") return d.stage === "successful"
      if (oldFilter === "dropped") return d.stage === "dropped"
      return d.stage === "successful" || d.stage === "dropped"
    })
    const q = search.trim().toLowerCase()
    const filtered = q
      ? byTab.filter(
          (d) =>
            d.name.toLowerCase().includes(q) ||
            d.short_code.toLowerCase().includes(q) ||
            d.borrower.toLowerCase().includes(q),
        )
      : byTab
    return [...filtered].sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
    )
  }, [deals, tab, oldFilter, search])

  return (
    <div className="px-6 py-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-title-page text-text-primary">Deals</h1>
        {user?.role === "admin" && (
          <Button onClick={() => setDialogOpen(true)}>
            <Plus className="h-4 w-4" />
            New deal
          </Button>
        )}
      </div>

      <div className="rounded-lg border border-border bg-surface">
        <div className="flex h-10 items-center gap-6 border-b border-border px-4">
          {(["new", "running", "old"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={cn(
                "relative flex h-full items-center gap-1.5 text-body-strong capitalize",
                tab === t ? "text-brand-700" : "text-text-secondary",
              )}
            >
              {t === "new" ? "New" : t === "running" ? "Running" : "Old"}
              <span className="text-meta font-normal text-text-tertiary">{counts[t]}</span>
              {tab === t && (
                <span className="absolute -bottom-[1px] left-0 right-0 h-0.5 bg-brand-600" />
              )}
            </button>
          ))}
        </div>

        <div className="flex h-10 items-center gap-3 border-b border-border px-4">
          {tab === "old" && (
            <div className="flex gap-1">
              {(["all", "successful", "dropped"] as const).map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setOldFilter(f)}
                  className={cn(
                    "rounded-md px-2 py-1 text-[13px] font-medium capitalize",
                    oldFilter === f
                      ? "bg-brand-50 text-brand-700"
                      : "text-text-secondary hover:bg-surface-hover",
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
          )}
          <div className="relative w-60">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-tertiary" />
            <input
              placeholder="Search deals…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 w-full rounded-md border border-border bg-surface pl-8 pr-2 text-table text-text-primary placeholder:text-text-tertiary focus:outline-none focus:ring-2 focus:ring-brand-600"
            />
          </div>
          <span className="ml-auto text-meta text-text-tertiary">
            {rows.length} deal{rows.length === 1 ? "" : "s"}
          </span>
        </div>

        <table className="w-full">
          <thead>
            <tr className="h-9 bg-surface-sunken text-left text-label text-text-tertiary">
              <th className="px-4 font-medium">Deal</th>
              <th className="px-4 font-medium">Stage</th>
              <th className="px-4 text-right font-medium">Documents</th>
              {tab === "running" && <th className="px-4 text-right font-medium">Tasks</th>}
              <th className="px-4 text-right font-medium">Last activity</th>
              <th className="px-4 text-right font-medium">Created</th>
            </tr>
          </thead>
          <tbody>
            {isLoading &&
              [0, 1, 2].map((i) => (
                <tr key={i} className="h-10 border-t border-border">
                  <td colSpan={6} className="px-4">
                    <div className="h-3 w-1/3 animate-pulse rounded bg-surface-sunken" />
                  </td>
                </tr>
              ))}

            {!isLoading && rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center">
                  <EmptyStateFor tab={tab} isAdmin={user?.role === "admin"} onNewDeal={() => setDialogOpen(true)} />
                </td>
              </tr>
            )}

            {rows.map((deal) => (
              <DealRow key={deal.id} deal={deal} showTasks={tab === "running"} onOpen={() => navigate(`/deals/${deal.id}/documents`)} />
            ))}
          </tbody>
        </table>
      </div>

      <NewDealDialog open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  )
}

function DealRow({
  deal,
  showTasks,
  onOpen,
}: {
  deal: DealListItem
  showTasks: boolean
  onOpen: () => void
}) {
  return (
    <tr className="h-10 border-t border-border hover:bg-surface-hover">
      <td className="px-4">
        <button type="button" onClick={onOpen} className="text-left">
          <span className="block text-table font-medium text-text-primary">{deal.name}</span>
          <span className="block text-meta text-text-tertiary">
            {deal.short_code} · {deal.borrower}
          </span>
        </button>
      </td>
      <td className="px-4">
        <DealStagePill stage={deal.stage} />
      </td>
      <td className="px-4 text-right tabular-nums text-table text-text-secondary">
        {deal.document_count}
      </td>
      {showTasks && (
        <td className="px-4 text-right tabular-nums text-table text-text-secondary">
          {deal.tasks_done}/{deal.tasks_total}
        </td>
      )}
      <td className="px-4 text-right text-meta text-text-tertiary" title={formatDate(deal.updated_at)}>
        {relativeTime(deal.updated_at)}
      </td>
      <td className="px-4 text-right tabular-nums text-meta text-text-tertiary">
        {formatDate(deal.created_at)}
      </td>
    </tr>
  )
}

function EmptyStateFor({
  tab,
  isAdmin,
  onNewDeal,
}: {
  tab: HomeTab
  isAdmin: boolean
  onNewDeal: () => void
}) {
  if (tab === "new") {
    return isAdmin ? (
      <div className="flex flex-col items-center gap-3">
        <div>
          <p className="text-body-strong text-text-primary">No new deals</p>
          <p className="text-table text-text-secondary">Deals you create start here.</p>
        </div>
        <Button onClick={onNewDeal} size="sm">
          <Plus className="h-4 w-4" />
          New deal
        </Button>
      </div>
    ) : (
      <div>
        <p className="text-body-strong text-text-primary">No new deals</p>
        <p className="text-table text-text-secondary">Samir adds new deals here.</p>
      </div>
    )
  }
  if (tab === "running") {
    return (
      <div>
        <p className="text-body-strong text-text-primary">No running deals</p>
        <p className="text-table text-text-secondary">Deals move here when work starts.</p>
      </div>
    )
  }
  return (
    <div>
      <p className="text-body-strong text-text-primary">No closed deals</p>
      <p className="text-table text-text-secondary">Successful and dropped deals appear here.</p>
    </div>
  )
}
