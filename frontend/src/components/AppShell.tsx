import { useState, type ReactNode } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import {
  Archive as ArchiveIcon,
  CheckSquare,
  Clock,
  FolderClosed,
  Layers,
  ShieldCheck,
  Users as UsersIcon,
} from "lucide-react"
import { useQueryClient } from "@tanstack/react-query"
import { logout } from "@/api/auth"
import { useApprovals } from "@/api/approvals"
import { useDeals } from "@/api/deals"
import { useMyTasks } from "@/api/tasks"
import { useAuthStore } from "@/stores/auth"
import { cn, initials } from "@/lib/utils"

function NavRow({
  to,
  icon: Icon,
  label,
  count,
  isApprovalBadge = false,
  active,
}: {
  to: string
  icon: typeof Layers
  label: string
  count?: number
  isApprovalBadge?: boolean
  active: boolean
}) {
  const showCount = count !== undefined && (!isApprovalBadge || count > 0)
  return (
    <Link
      to={to}
      className={cn(
        "relative flex h-9 items-center gap-2 rounded-md px-3 text-body-strong",
        active ? "bg-brand-50 text-brand-700" : "text-text-secondary hover:bg-surface-hover",
      )}
    >
      {active && <span className="absolute left-0 top-0 h-full w-[3px] rounded-r bg-brand-600" />}
      <Icon className="h-4 w-4" aria-hidden />
      <span className="flex-1">{label}</span>
      {showCount && (
        <span
          className={cn(
            "rounded-full px-2 py-0.5 text-[11px] font-semibold",
            isApprovalBadge ? "bg-brand-700 text-white" : "bg-[#EEF0EE] text-text-tertiary",
          )}
        >
          {count}
        </span>
      )}
    </Link>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const user = useAuthStore((s) => s.user)
  const clear = useAuthStore((s) => s.clear)
  const [menuOpen, setMenuOpen] = useState(false)

  const { data: deals } = useDeals()
  const { data: myTasks } = useMyTasks()
  const { data: approvals } = useApprovals()
  const isAdmin = user?.role === "admin"

  async function handleLogout() {
    await logout()
    clear()
    qc.clear()
    navigate("/login")
  }

  return (
    <div className="min-h-screen bg-canvas">
      <header className="flex h-12 items-center justify-between border-b border-border bg-surface px-6">
        <div className="flex items-center gap-2">
          <div className="flex h-5 w-5 items-center justify-center rounded bg-brand-600 text-[11px] font-semibold text-white">
            L
          </div>
          <span className="text-title-section text-text-primary">Lilkis Deal Room</span>
        </div>

        <div className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            className="flex items-center gap-2"
          >
            <span
              className="flex h-6 w-6 items-center justify-center rounded-full bg-pill-neutral-bg text-[11px] font-semibold text-text-primary"
              aria-hidden
            >
              {user ? initials(user.display_name) : ""}
            </span>
            <span className="text-left">
              <span className="block text-body-strong text-text-primary">{user?.display_name}</span>
              <span className="block text-meta text-text-tertiary">
                {isAdmin ? "Admin" : "Member"}
              </span>
            </span>
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-10 w-44 rounded-md border border-border bg-surface py-1 shadow-[0_4px_12px_rgba(16,24,16,.08),0_0_0_1px_#E3E6E3]">
              <Link
                to="/change-password"
                onClick={() => setMenuOpen(false)}
                className="block px-3 py-2 text-body text-text-primary hover:bg-surface-hover"
              >
                Change password
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                className="block w-full px-3 py-2 text-left text-body text-text-primary hover:bg-surface-hover"
              >
                Log out
              </button>
            </div>
          )}
        </div>
      </header>

      <div className="flex">
        <nav className="fixed bottom-0 left-0 top-12 w-[232px] overflow-y-auto border-r border-border bg-surface p-3">
          <div className="flex flex-col gap-1">
            <NavRow
              to="/deals"
              icon={Layers}
              label="Deals"
              count={deals?.length}
              active={location.pathname.startsWith("/deals")}
            />
            <NavRow
              to="/my-tasks"
              icon={CheckSquare}
              label="My Tasks"
              count={myTasks?.length}
              active={location.pathname === "/my-tasks"}
            />
          </div>

          {isAdmin && (
            <div className="mt-6">
              <div className="px-3 pb-1 text-[11px] font-medium uppercase tracking-wide text-text-tertiary">
                Admin
              </div>
              <div className="flex flex-col gap-1">
                <NavRow
                  to="/admin/approvals"
                  icon={ShieldCheck}
                  label="Approvals"
                  count={approvals?.length}
                  isApprovalBadge
                  active={location.pathname === "/admin/approvals"}
                />
                <NavRow
                  to="/admin/folders"
                  icon={FolderClosed}
                  label="Folders"
                  active={location.pathname === "/admin/folders"}
                />
                <NavRow
                  to="/admin/users"
                  icon={UsersIcon}
                  label="Users & permissions"
                  active={location.pathname === "/admin/users"}
                />
                <NavRow
                  to="/admin/archive"
                  icon={ArchiveIcon}
                  label="Archive"
                  active={location.pathname === "/admin/archive"}
                />
                <NavRow
                  to="/admin/activity"
                  icon={Clock}
                  label="Activity"
                  active={location.pathname === "/admin/activity"}
                />
              </div>
            </div>
          )}
        </nav>

        <main className="ml-[232px] flex-1">{children}</main>
      </div>
    </div>
  )
}
