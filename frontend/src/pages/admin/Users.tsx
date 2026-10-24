import { useState } from "react"
import { useAdminUsers, useCreateUser, usePermissionMatrix, useResetPassword, useSetPermission, useUpdateUser } from "@/api/admin"
import { useFolders } from "@/api/folders"
import { useAuthStore } from "@/stores/auth"
import { Button } from "@/components/ui/button"
import { PageBody } from "@/components/PageBody"
import { UseALaptop } from "@/components/UseALaptop"
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

// DESIGN §6.9: "Temporary password (generated 14 characters, with Copy
// and Regenerate)". Generated in the browser and shown before the user is
// created, so the admin can copy it while they are still on the phone to
// the person — the server accepts it as temporary_password rather than
// inventing its own.
const PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"

function generatePassword(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(14))
  // No 0/O/1/l/I: this gets read down a phone line.
  return Array.from(bytes, (b) => PASSWORD_ALPHABET[b % PASSWORD_ALPHABET.length]).join("")
}

function AddUserDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const createUser = useCreateUser()
  const me = useAuthStore((s) => s.user)
  const { data: users } = useAdminUsers()
  const { data: permissions } = usePermissionMatrix()
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [role, setRole] = useState<"admin" | "member">("member")
  const [canApprove, setCanApprove] = useState(false)
  const [password, setPassword] = useState(generatePassword)
  const [copyFrom, setCopyFrom] = useState("")
  const [copied, setCopied] = useState(false)
  const [result, setResult] = useState<{ email: string; temporary_password: string } | null>(null)

  const ownerName = (users ?? []).find((u) => u.is_owner)?.display_name

  // "Copy folder access from (a user, or Set manually)" — read off the
  // permission matrix that is already loaded for the other tab.
  const folderLevels =
    copyFrom === ""
      ? {}
      : Object.fromEntries(
          (permissions ?? [])
            .filter((row) => row.user_id === copyFrom)
            .map((row) => [row.folder_id, row.access_level]),
        )

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const res = await createUser.mutateAsync({
      display_name: name,
      email,
      role,
      can_approve: canApprove,
      temporary_password: password,
      folder_levels: folderLevels,
    })
    setResult(res)
  }

  function handleClose() {
    setName("")
    setEmail("")
    setRole("member")
    setCanApprove(false)
    setPassword(generatePassword())
    setCopyFrom("")
    setCopied(false)
    setResult(null)
    onOpenChange(false)
  }

  if (result) {
    return (
      <Dialog open={open} onOpenChange={handleClose} title="User created" width={440}>
        <p className="text-body text-text-secondary">
          {name || "They"} can sign in with this straight away.
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
        {/* Only the owner mints admins — otherwise the rule on the row
            menu is worth nothing, since any admin could create a second
            admin account here instead. The API refuses it either way. */}
        <Field label="Role" htmlFor="u-role">
          {me?.is_owner ? (
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
          ) : (
            <p className="text-body text-text-secondary">
              Member. Only {ownerName ?? "the owner"} can add an admin.
            </p>
          )}
        </Field>
        <label className="flex items-center gap-2 text-body text-text-primary">
          <input type="checkbox" checked={canApprove} onChange={(e) => setCanApprove(e.target.checked)} />
          Can approve requests
        </label>

        <Field
          label="Temporary password"
          htmlFor="u-password"
          helper="Give them this password directly. They'll choose a new one when they first sign in."
        >
          <div className="flex gap-2">
            <Input id="u-password" readOnly value={password} className="font-mono" />
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={async () => {
                await navigator.clipboard.writeText(password)
                setCopied(true)
                setTimeout(() => setCopied(false), 2000)
              }}
            >
              {copied ? "Copied" : "Copy"}
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => {
                setPassword(generatePassword())
                setCopied(false)
              }}
            >
              Regenerate
            </Button>
          </div>
        </Field>

        <Field
          label="Copy folder access from"
          htmlFor="u-copy"
          helper="Or set it manually afterwards in Folder access."
        >
          <select
            id="u-copy"
            value={copyFrom}
            onChange={(e) => setCopyFrom(e.target.value)}
            className="h-9 rounded-md border border-border-strong bg-surface px-2 text-body text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-600"
          >
            <option value="">Set manually</option>
            {(users ?? [])
              .filter((u) => u.is_active)
              .map((u) => (
                <option key={u.id} value={u.id}>
                  {u.display_name}
                </option>
              ))}
          </select>
        </Field>

        <DialogFooter>
          <Button type="button" variant="secondary" onClick={handleClose}>
            Cancel
          </Button>
          <Button type="submit" loading={createUser.isPending}>
            Add user
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  )
}

function UserRow({ user }: { user: UserAdmin }) {
  const me = useAuthStore((s) => s.user)
  const updateUser = useUpdateUser()
  const resetPassword = useResetPassword()
  const [resetResult, setResetResult] = useState<string | null>(null)
  const [roleConfirm, setRoleConfirm] = useState(false)

  // The same three rules the API enforces (admin._guard_access_change),
  // mirrored here only so the menu doesn't offer what the server will
  // refuse. CLAUDE.md §2.3: this is not the enforcement.
  const isSelf = me?.id === user.id
  const canChangeAccess = !user.is_owner && !isSelf
  const canChangeRole = canChangeAccess && !!me?.is_owner
  const promoting = user.role === "member"

  return (
    <tr className="group h-10 border-t border-border hover:bg-surface-hover">
      <td className="px-4 text-table font-medium text-text-primary">
        {user.display_name}
        {!user.is_active && <span className="ml-1 text-text-tertiary">(deactivated)</span>}
      </td>
      <td className="px-4 text-table text-text-secondary">{user.email}</td>
      <td className="px-4 text-table capitalize text-text-secondary">
        {user.role}
        {/* Says why this row has no role actions, rather than leaving an
            admin to wonder why the menu is shorter here. */}
        {user.is_owner && (
          <span className="ml-1.5 rounded bg-pill-neutral-bg px-1.5 py-0.5 text-meta uppercase tracking-wide text-pill-neutral-text">
            Owner
          </span>
        )}
      </td>
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
          {canChangeRole && (
            <RowMenuItem onSelect={() => setRoleConfirm(true)}>
              {promoting ? "Make admin" : "Make member"}
            </RowMenuItem>
          )}
          {canChangeAccess && (
            <RowMenuItem
              danger={user.is_active}
              onSelect={() => updateUser.mutate({ userId: user.id, is_active: !user.is_active })}
            >
              {user.is_active ? "Deactivate" : "Reactivate"}
            </RowMenuItem>
          )}
        </RowMenu>
      </td>

      {/* Admin is full access to every folder, Borrower details included,
          and it is one click away in a menu next to "Reset password".
          Worth a sentence and a second click. */}
      <Dialog
        open={roleConfirm}
        onOpenChange={setRoleConfirm}
        title={promoting ? `Make ${user.display_name} an admin?` : `Make ${user.display_name} a member?`}
        width={440}
      >
        <p className="text-body text-text-secondary">
          {promoting
            ? "Admins see and change every folder in every deal, including ones this person has no access to today, and can manage folders, settings and the Archive."
            : "They keep their account and their folder access, but lose the Archive, Activity, deal stages and everything else under Admin."}
        </p>
        <DialogFooter>
          <Button variant="secondary" onClick={() => setRoleConfirm(false)}>
            Cancel
          </Button>
          <Button
            loading={updateUser.isPending}
            onClick={async () => {
              await updateUser.mutateAsync({
                userId: user.id,
                role: promoting ? "admin" : "member",
              })
              setRoleConfirm(false)
            }}
          >
            {promoting ? "Make admin" : "Make member"}
          </Button>
        </DialogFooter>
      </Dialog>

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
    return (
      matrix?.find((m) => m.user_id === userId && m.folder_id === folderId)?.access_level ?? "none"
    ) as AccessLevel
  }

  return (
    <>
      <UseALaptop what="The permission matrix is too wide to use on a phone." />
      <div className="w-full max-w-full overflow-x-auto rounded-md border border-border max-md:hidden">
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
    </>
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
