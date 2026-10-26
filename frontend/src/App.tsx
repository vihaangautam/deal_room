import { useEffect, type ReactNode } from "react"
import { Navigate, Route, Routes } from "react-router-dom"
import { fetchMe } from "@/api/auth"
import { useAuthStore } from "@/stores/auth"
import { AppShell } from "@/components/AppShell"
import { Login } from "@/pages/Login"
import { ChangePassword } from "@/pages/ChangePassword"
import { DealsHome } from "@/pages/DealsHome"
import { DealDocuments } from "@/pages/DealDocuments"
import { DealActivity } from "@/pages/DealActivity"
import { DealComments } from "@/pages/DealComments"
import { DealTasks } from "@/pages/DealTasks"
import { TaskDetail } from "@/pages/TaskDetail"
import { MyTasks } from "@/pages/MyTasks"
import { Approvals } from "@/pages/admin/Approvals"
import { Folders } from "@/pages/admin/Folders"
import { Users } from "@/pages/admin/Users"
import { Archive } from "@/pages/admin/Archive"
import { Activity } from "@/pages/admin/Activity"

// Typing /admin/users as a member used to render the page frame, the tabs
// and an "Add user" button over an empty table, because every /admin
// request behind it 403s. No data crosses — CLAUDE.md §2.3 is clear that
// the frontend is not the enforcement and this does not change that — it
// just looks broken instead of saying no.
function RequireAdmin({ children }: { children: ReactNode }) {
  const user = useAuthStore((s) => s.user)
  if (user && user.role !== "admin") return <Navigate to="/deals" replace />
  return <>{children}</>
}

// Approvals is NOT admin-only. PRD §7 gives "Approve/reject requests" to
// anyone with can_approve, whatever their role, and require_approver on
// the API agrees. Gating this on admin would lock an approver out of the
// one screen their permission exists for.
function RequireApprover({ children }: { children: ReactNode }) {
  const user = useAuthStore((s) => s.user)
  if (user && user.role !== "admin" && !user.can_approve) {
    return <Navigate to="/deals" replace />
  }
  return <>{children}</>
}

function ProtectedRoutes() {
  const status = useAuthStore((s) => s.status)
  const user = useAuthStore((s) => s.user)

  if (status === "loading") {
    return null // AppShell-less blank frame while /auth/me resolves
  }
  if (status === "anonymous") {
    return <Navigate to="/login" replace />
  }
  if (user?.must_change_password) {
    return <Navigate to="/change-password" replace />
  }

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/deals" replace />} />
        <Route path="/deals" element={<DealsHome />} />
        <Route path="/deals/:dealId/documents/:folderId?" element={<DealDocuments />} />
        <Route path="/deals/:dealId/tasks" element={<DealTasks />} />
        <Route path="/deals/:dealId/comments" element={<DealComments />} />
        <Route path="/deals/:dealId/activity" element={<DealActivity />} />
        <Route path="/deals/:dealId/tasks/:taskId" element={<TaskDetail />} />
        <Route path="/my-tasks" element={<MyTasks />} />
        <Route
          path="/admin/approvals"
          element={
            <RequireApprover>
              <Approvals />
            </RequireApprover>
          }
        />
        <Route path="/admin/folders" element={<RequireAdmin><Folders /></RequireAdmin>} />
        <Route path="/admin/users" element={<RequireAdmin><Users /></RequireAdmin>} />
        <Route path="/admin/archive" element={<RequireAdmin><Archive /></RequireAdmin>} />
        <Route path="/admin/activity" element={<RequireAdmin><Activity /></RequireAdmin>} />
        {/* Anything else under /admin, now and later. */}
        <Route path="/admin/*" element={<Navigate to="/deals" replace />} />
      </Routes>
    </AppShell>
  )
}

export default function App() {
  const setUser = useAuthStore((s) => s.setUser)
  const clear = useAuthStore((s) => s.clear)

  useEffect(() => {
    fetchMe().then(setUser).catch(() => clear())
  }, [setUser, clear])

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/change-password" element={<ChangePassword />} />
      <Route path="/*" element={<ProtectedRoutes />} />
    </Routes>
  )
}
