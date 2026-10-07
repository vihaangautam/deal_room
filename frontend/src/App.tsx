import { useEffect } from "react"
import { Navigate, Route, Routes } from "react-router-dom"
import { fetchMe } from "@/api/auth"
import { useAuthStore } from "@/stores/auth"
import { AppShell } from "@/components/AppShell"
import { Login } from "@/pages/Login"
import { ChangePassword } from "@/pages/ChangePassword"
import { DealsHome } from "@/pages/DealsHome"
import { DealDocuments } from "@/pages/DealDocuments"
import { DealActivity } from "@/pages/DealActivity"
import { DealTasks } from "@/pages/DealTasks"
import { TaskDetail } from "@/pages/TaskDetail"
import { MyTasks } from "@/pages/MyTasks"
import { Approvals } from "@/pages/admin/Approvals"
import { Folders } from "@/pages/admin/Folders"
import { Users } from "@/pages/admin/Users"
import { Archive } from "@/pages/admin/Archive"
import { Activity } from "@/pages/admin/Activity"

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
        <Route path="/deals/:dealId/activity" element={<DealActivity />} />
        <Route path="/deals/:dealId/tasks/:taskId" element={<TaskDetail />} />
        <Route path="/my-tasks" element={<MyTasks />} />
        <Route path="/admin/approvals" element={<Approvals />} />
        <Route path="/admin/folders" element={<Folders />} />
        <Route path="/admin/users" element={<Users />} />
        <Route path="/admin/archive" element={<Archive />} />
        <Route path="/admin/activity" element={<Activity />} />
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
