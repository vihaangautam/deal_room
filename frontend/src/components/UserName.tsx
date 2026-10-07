import { useMemo } from "react"
import { useUsers } from "@/api/users"

/**
 * PRD §10: "Deactivated users stay in history and on assignments, marked
 * (deactivated)." DESIGN §6.9 puts that tag in --text-tertiary wherever
 * the name appears — not only on the Users table, which was the one place
 * doing it.
 *
 * Most payloads carry a name and no id (assignee_name, uploaded_by_name,
 * requested_by_name), so the lookup falls back to matching on the name.
 * Two people with the same display name would both get tagged; the fix
 * for that is an id on those payloads, not a cleverer match here.
 */
function useDeactivated() {
  const { data: users } = useUsers()
  return useMemo(() => {
    const ids = new Set<string>()
    const names = new Set<string>()
    for (const user of users ?? []) {
      if (user.is_active) continue
      ids.add(user.id)
      names.add(user.display_name)
    }
    return { ids, names }
  }, [users])
}

export function UserName({
  name,
  id,
  fallback = "—",
}: {
  name: string | null | undefined
  id?: string | null
  /** Shown when there is no name at all, e.g. an unassigned task. */
  fallback?: string
}) {
  const { ids, names } = useDeactivated()
  if (!name) return <>{fallback}</>

  const deactivated = id ? ids.has(id) : names.has(name)
  return (
    <>
      {name}
      {deactivated && <span className="ml-1 text-text-tertiary">(deactivated)</span>}
    </>
  )
}
