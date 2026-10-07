import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { changePassword, fetchMe } from "@/api/auth"
import { ApiError } from "@/api/client"
import { useAuthStore } from "@/stores/auth"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Field } from "@/components/ui/field"

export function ChangePassword() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const setUser = useAuthStore((s) => s.setUser)
  const forced = user?.must_change_password ?? false

  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (newPassword.length < 10) {
      setError("At least 10 characters.")
      return
    }
    if (newPassword !== confirm) {
      setError("Passwords don't match.")
      return
    }

    setSubmitting(true)
    try {
      await changePassword(newPassword, forced ? undefined : currentPassword)
      const refreshed = await fetchMe()
      setUser(refreshed)
      navigate("/deals")
    } catch (err) {
      setError(
        err instanceof ApiError && typeof err.detail === "string"
          ? err.detail
          : "Couldn't reach the server. Check your connection and try again.",
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-start bg-canvas pt-[15vh]">
      <div className="mx-auto w-full max-w-[400px] rounded-lg border border-border bg-surface p-8 sm:ml-[40%] sm:mr-auto">
        <h1 className="mb-6 text-title-page text-text-primary">Choose a new password</h1>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {error && <p className="text-body text-text-danger">{error}</p>}

          {!forced && (
            <Field label="Current password" htmlFor="current">
              <Input
                id="current"
                type="password"
                autoComplete="current-password"
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
              />
            </Field>
          )}

          <Field label="New password" htmlFor="new" helper="At least 10 characters.">
            <Input
              id="new"
              type="password"
              autoComplete="new-password"
              required
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </Field>

          <Field label="Confirm" htmlFor="confirm">
            <Input
              id="confirm"
              type="password"
              autoComplete="new-password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </Field>

          <Button type="submit" className="w-full" loading={submitting}>
            Set new password
          </Button>
        </form>
      </div>
    </div>
  )
}
