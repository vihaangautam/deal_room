import { type ReactNode } from "react"
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
import { Menu, RowMenuItem } from "@/components/ui/dropdown-menu"
import { Avatar } from "@/components/ui/avatar"
import { cn } from "@/lib/utils"

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
  count?: number | undefined
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
      {/* In the sidebar's 8px padding, flush to its edge — not inset to
          the row, which left it floating in the middle of the gutter. */}
      {active && <span className="absolute -left-2 top-0 h-full w-[3px] rounded-r bg-brand-600" />}
      <Icon className="h-4 w-4" aria-hidden />
      <span className="flex-1">{label}</span>
      {showCount && (
        <span
          className={cn(
            "flex items-center justify-center rounded-full text-[11px] font-semibold",
            isApprovalBadge
              ? "h-5 w-5 bg-brand-700 text-white"
              : "h-5 min-w-5 px-1.5 bg-[#EEF0EE] text-text-tertiary",
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

  const { data: deals } = useDeals()
  const { data: myTasks } = useMyTasks()
  const { data: approvals } = useApprovals()
  const isAdmin = user?.role === "admin"

  async function handleLogout() {
    try {
      await logout()
    } finally {
      // An already-expired session makes /auth/logout itself fail, and
      // without this the throw skipped the clear and left the user
      // staring at a shell they could not leave.
      clear()
      qc.clear()
      navigate("/login")
    }
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

        <Menu
          align="end"
          trigger={
            <button type="button" className="flex items-center gap-2">
              <Avatar name={user?.display_name ?? ""} id={user?.id} />
              <span className="text-left">
                <span className="block text-body-strong text-text-primary">{user?.display_name}</span>
                <span className="block text-meta text-text-tertiary">
                  {isAdmin ? "Admin" : "Member"}
                </span>
              </span>
            </button>
          }
        >
          <RowMenuItem onSelect={() => navigate("/change-password")}>Change password</RowMenuItem>
          <RowMenuItem onSelect={handleLogout}>Log out</RowMenuItem>
        </Menu>
      </header>

      <div className="flex">
        <nav className="fixed bottom-0 left-0 top-12 w-[232px] overflow-y-auto border-r border-border bg-surface p-2">
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

        <main className="ml-[232px] flex-1 min-w-0">{children}</main>
      </div>
    </div>
  )
}
