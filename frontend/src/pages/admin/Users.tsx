import { useState } from "react"
import { useAdminUsers, useCreateUser, usePermissionMatrix, useResetPassword, useSetPermission, useUpdateUser } from "@/api/admin"
import { useFolders } from "@/api/folders"
import { Button } from "@/components/ui/button"
import { PageBody } from "@/components/PageBody"
import { Tab, TabBand } from "@/components/TabBand"
import { TableFooter } from "@/components/TableFooter"
import { PageHeader } from "@/components/PageHeader"
import { Input } from "@/components/ui/input"
import { Field } from "@/components/ui/field"
import { Dialog, DialogFooter } from "@/components/ui/dialog"
import { RowMenu, RowMenuItem } from "@/components/ui/dropdown-menu"
import { cn, formatDateTime } from "@/lib/utils"
import type { AccessLevel, UserAdmin } from "@/api/types"

const ACCESS_LEVELS: AccessLevel[] = ["none", "view", "contribute"]
const ACCESS_STYLE: Record<AccessLevel, string> = {
  none: "bg-pill-neutral-bg text-pill-neutral-text",
  view: "bg-pill-info-bg text-pill-info-text",
  contribute: "bg-pill-success-bg text-pill-success-text",
}
const ACCESS_LABEL: Record<AccessLevel, string> = { none: "None", view: "View", contribute: "Contribute" }

function AddUserDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const createUser = useCreateUser()
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [role, setRole] = useState<"admin" | "member">("member")
  const [canApprove, setCanApprove] = useState(false)
  const [result, setResult] = useState<{ email: string; temporary_password: string } | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const res = await createUser.mutateAsync({
      display_name: name,
      email,
      role,
      can_approve: canApprove,
      folder_levels: {},
    })
    setResult(res)
  }

  function handleClose() {
    setName("")
    setEmail("")
    setRole("member")
    setCanApprove(false)
    setResult(null)
    onOpenChange(false)
  }

  if (result) {
    return (
      <Dialog open={open} onOpenChange={handleClose} title="User created" width={440}>
        <p className="text-body text-text-secondary">
          Give them this password directly. They&apos;ll choose a new one when they first sign in.
        </p>
        <div className="mt-3 rounded-md bg-surface-sunken p-3">
          <p className="text-meta text-text-tertiary">{result.email}</p>
          <p className="font-mono text-body-strong text-text-primary">{result.temporary_password}</p>
        </div>
        <DialogFooter>
          <Button onClick={handleClose}>Done</Button>
        </DialogFooter>
      </Dialog>
    )
  }

  return (
    <Dialog open={open} onOpenChange={handleClose} title="Add user" width={480}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Field label="Full name" htmlFor="u-name">
          <Input id="u-name" required value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Email" htmlFor="u-email">
          <Input id="u-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Role" htmlFor="u-role">
          <div className="flex gap-4">
            <label className="flex items-center gap-1.5 text-body text-text-primary">
              <input type="radio" checked={role === "member"} onChange={() => setRole("member")} />
              Member
            </label>
            <label className="flex items-center gap-1.5 text-body text-text-primary">
              <input type="radio" checked={role === "admin"} onChange={() => setRole("admin")} />
              Admin
            </label>
          </div>
        </Field>
        <label className="flex items-center gap-2 text-body text-text-primary">
          <input type="checkbox" checked={canApprove} onChange={(e) => setCanApprove(e.target.checked)} />
          Can approve requests
        </label>
        <DialogFooter>
          <Button type="button" variant="secondary" onClick={handleClose}>
            Cancel
          </Button>
          <Button type="submit" loading={createUser.isPending}>
            Save
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  )
}

function UserRow({ user }: { user: UserAdmin }) {
  const updateUser = useUpdateUser()
  const resetPassword = useResetPassword()
  const [resetResult, setResetResult] = useState<string | null>(null)

  return (
    <tr className="h-10 border-t border-border hover:bg-surface-hover">
      <td className="px-4 text-table font-medium text-text-primary">
        {user.display_name}
        {!user.is_active && <span className="ml-1 text-text-tertiary">(deactivated)</span>}
      </td>
      <td className="px-4 text-table text-text-secondary">{user.email}</td>
      <td className="px-4 text-table capitalize text-text-secondary">{user.role}</td>
      <td className="px-4 text-table text-text-secondary">{user.can_approve ? "Yes" : "No"}</td>
      <td className="px-4 text-table text-text-secondary">{user.is_active ? "Active" : "Deactivated"}</td>
      <td className="px-4 text-table text-text-tertiary">
        {user.last_login_at ? formatDateTime(user.last_login_at) : "Never"}
      </td>
      <td className="w-10 px-2">
        <RowMenu>
          <RowMenuItem
            onSelect={async () => {
              const res = await resetPassword.mutateAsync(user.id)
              setResetResult(res.temporary_password)
            }}
          >
            Reset password
          </RowMenuItem>
          <RowMenuItem onSelect={() => updateUser.mutate({ userId: user.id, is_active: !user.is_active })}>
            {user.is_active ? "Deactivate" : "Reactivate"}
          </RowMenuItem>
        </RowMenu>
      </td>

      <Dialog open={resetResult !== null} onOpenChange={() => setResetResult(null)} title="Password reset" width={400}>
        <p className="text-body text-text-secondary">New temporary password for {user.display_name}:</p>
        <p className="mt-2 font-mono text-body-strong text-text-primary">{resetResult}</p>
        <DialogFooter>
          <Button onClick={() => setResetResult(null)}>Done</Button>
        </DialogFooter>
      </Dialog>
    </tr>
  )
}

function UsersTab({ addOpen, setAddOpen }: { addOpen: boolean; setAddOpen: (v: boolean) => void }) {
  const { data: users, isLoading } = useAdminUsers()

  return (
    <div>
      <div className="rounded-md border border-border">
        <table className="w-full">
          <thead>
            <tr className="h-9 bg-surface-sunken text-left text-label text-text-tertiary">
              <th className="px-4 font-medium">Name</th>
              <th className="px-4 font-medium">Email</th>
              <th className="px-4 font-medium">Role</th>
              <th className="px-4 font-medium">Can approve</th>
              <th className="px-4 font-medium">Status</th>
              <th className="px-4 font-medium">Last login</th>
              <th className="w-10 px-2" />
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr className="h-10 border-t border-border">
                <td colSpan={7} className="px-4">
                  <div className="h-3 w-1/3 animate-pulse rounded bg-surface-sunken" />
                </td>
              </tr>
            )}
            {users?.map((u) => (
              <UserRow key={u.id} user={u} />
            ))}
          </tbody>
        </table>
        <TableFooter count={users?.length ?? 0} noun="user" />
      </div>
      <AddUserDialog open={addOpen} onOpenChange={setAddOpen} />
    </div>
  )
}

function PermissionMatrixTab() {
  const { data: folders } = useFolders()
  const { data: matrix } = usePermissionMatrix()
  const { data: users } = useAdminUsers()
  const setPermission = useSetPermission()

  function levelFor(userId: string, folderId: string): AccessLevel {
    return (matrix?.find((m) => m.user_id === userId && m.folder_id === folderId)?.access_level ?? "none") as AccessLevel
  }

  return (
    <div className="w-full max-w-full overflow-x-auto rounded-md border border-border">
      <table className="w-max min-w-full border-separate border-spacing-0">
        <thead>
          <tr className="h-10 bg-surface-sunken text-left text-label text-text-tertiary">
            <th className="sticky left-0 z-20 w-[180px] min-w-[180px] bg-surface-sunken px-4 font-medium border-b border-r border-border shadow-[1px_0_0_0_#EEF0EE]">
              User
            </th>
            {folders?.map((f) => (
              <th
                key={f.id}
                className="min-w-[160px] max-w-[220px] px-3 py-2 text-center font-medium border-b border-r border-border last:border-r-0"
              >
                <span className="block truncate text-label text-text-primary" title={f.name}>
                  {f.name}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {users?.map((user) => (
            <tr key={user.id} className="h-10 hover:bg-surface-hover">
              <td className="sticky left-0 z-10 w-[180px] min-w-[180px] bg-surface px-4 text-table font-medium text-text-primary border-b border-r border-border shadow-[1px_0_0_0_#EEF0EE]">
                {user.display_name}
              </td>
              {folders?.map((folder) => {
                if (user.role === "admin") {
                  return (
                    <td
                      key={folder.id}
                      className="min-w-[160px] px-3 py-2 text-center text-meta text-text-tertiary border-b border-r border-border last:border-r-0"
                    >
                      Full access
                    </td>
                  )
                }
                const level = levelFor(user.id, folder.id)
                return (
                  <td
                    key={folder.id}
                    className="min-w-[160px] px-3 py-2 text-center border-b border-r border-border last:border-r-0"
                  >
                    <div className="flex justify-center gap-1">
                      {ACCESS_LEVELS.map((l) => (
                        <button
                          key={l}
                          type="button"
                          title={ACCESS_LABEL[l]}
                          onClick={() =>
                            setPermission.mutate({ userId: user.id, folderId: folder.id, accessLevel: l })
                          }
                          className={cn(
                            "h-6 w-6 rounded text-[10px] font-semibold transition-colors",
                            level === l ? ACCESS_STYLE[l] : "bg-surface-sunken text-text-tertiary hover:bg-[#E2E6E2]",
                          )}
                        >
                          {l[0]?.toUpperCase()}
                        </button>
                      ))}
                    </div>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Users() {
  const [tab, setTab] = useState<"users" | "permissions">("users")
  const [addOpen, setAddOpen] = useState(false)

  return (
    <>
      <PageHeader
        title="Users & permissions"
        actions={
          tab === "users" && <Button onClick={() => setAddOpen(true)}>Add user</Button>
        }
      />
      <TabBand
        tabs={(["users", "permissions"] as const).map((t) => (
          <Tab key={t} active={tab === t} onClick={() => setTab(t)}>
            {t === "users" ? "Users" : "Folder access"}
          </Tab>
        ))}
      />
      <PageBody>
      {tab === "users" ? (
        <UsersTab addOpen={addOpen} setAddOpen={setAddOpen} />
      ) : (
        <PermissionMatrixTab />
      )}
      </PageBody>
    </>
  )
}
