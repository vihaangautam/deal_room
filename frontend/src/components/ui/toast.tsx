import { useEffect } from "react"
import { create } from "zustand"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

// DESIGN.md §5.12. Zustand rather than context because CLAUDE.md §6.2's
// rule is about server state — toasts are neither server state nor auth,
// and they get raised from api/*.ts mutation callbacks that aren't inside
// a component, where a context hook can't reach.

type ToastTone = "success" | "info" | "warning"

export interface Toast {
  id: number
  message: string
  tone: ToastTone
  // DESIGN.md §5.12: "Include Undo wherever an undo exists (rename, for
  // instance)." The toast doesn't know how to undo anything — the caller
  // hands it the action.
  undo?: () => void
}

const MAX_STACKED = 3 // DESIGN.md §5.12
const DISMISS_MS = 4000

interface ToastState {
  toasts: Toast[]
  dismiss: (id: number) => void
}

let nextId = 1

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))

/** Raise a toast from anywhere, including outside React. */
export function toast(message: string, options: { tone?: ToastTone; undo?: () => void } = {}): void {
  const entry: Toast = {
    id: nextId++,
    message,
    tone: options.tone ?? "success",
    ...(options.undo ? { undo: options.undo } : {}),
  }
  useToastStore.setState((s) => ({ toasts: [...s.toasts, entry].slice(-MAX_STACKED) }))
}

const TONE_BAR: Record<ToastTone, string> = {
  success: "bg-[#177A01]",
  info: "bg-[#1E5AA8]",
  warning: "bg-[#8A5A00]",
}

function ToastRow({ item }: { item: Toast }) {
  const dismiss = useToastStore((s) => s.dismiss)

  useEffect(() => {
    // "Success auto-dismisses at 4s." Nothing here is an error — DESIGN
    // §5.12 is explicit that errors needing action render inline instead
    // — so everything we show is safe to time out.
    const timer = setTimeout(() => dismiss(item.id), DISMISS_MS)
    return () => clearTimeout(timer)
  }, [item.id, dismiss])

  return (
    <div
      role="status"
      className="relative flex w-[360px] items-center gap-3 overflow-hidden rounded-md bg-surface py-3 pl-4 pr-3 shadow-[0_4px_12px_rgba(16,24,16,.08),0_0_0_1px_#E3E6E3]"
    >
      <span className={cn("absolute left-0 top-0 h-full w-[3px]", TONE_BAR[item.tone])} aria-hidden />
      <p className="flex-1 text-body text-text-primary">{item.message}</p>
      {item.undo && (
        <button
          type="button"
          className="shrink-0 text-body-strong text-brand-700 hover:underline"
          onClick={() => {
            item.undo?.()
            dismiss(item.id)
          }}
        >
          Undo
        </button>
      )}
      <button
        type="button"
        aria-label="Dismiss"
        className="shrink-0 text-text-tertiary hover:text-text-secondary"
        onClick={() => dismiss(item.id)}
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts)
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed bottom-4 right-4 z-[60] flex flex-col gap-2"
    >
      {toasts.map((item) => (
        <div key={item.id} className="pointer-events-auto">
          <ToastRow item={item} />
        </div>
      ))}
    </div>
  )
}
