import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { ApiError } from "@/api/client"
import { fetchMe, login } from "@/api/auth"
import { useAuthStore } from "@/stores/auth"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Field } from "@/components/ui/field"

interface LoginErrorDetail {
  message: string
  locked: boolean
}

function isLoginErrorDetail(detail: unknown): detail is LoginErrorDetail {
  return typeof detail === "object" && detail !== null && "locked" in detail
}

export function Login() {
  const navigate = useNavigate()
  const setUser = useAuthStore((s) => s.setUser)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(email, password)
      const user = await fetchMe()
      setUser(user)
      navigate(user.must_change_password ? "/change-password" : "/deals")
    } catch (err) {
      // DESIGN.md §6.1: identical wording for unknown email, wrong
      // password and lockout — "Try again in 15 minutes." is the one
      // thing that differs, appended only when locked.
      if (err instanceof ApiError && isLoginErrorDetail(err.detail)) {
        setError(
          err.detail.locked
            ? "Email or password is incorrect. Try again in 15 minutes."
            : "Email or password is incorrect.",
        )
      } else {
        setError("Couldn't reach the server. Check your connection and try again.")
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-start bg-canvas pt-[15vh]">
      <div className="mx-auto w-full max-w-[400px] rounded-lg border border-border bg-surface p-8 sm:ml-[40%] sm:mr-auto">
        <div className="mb-6 flex items-center gap-2">
          <div className="flex h-5 w-5 items-center justify-center rounded bg-brand-600 text-[11px] font-semibold text-white">
            L
          </div>
          <span className="text-title-section text-text-primary">Lilkis Deal Room</span>
        </div>

        <h1 className="mb-6 text-title-page text-text-primary">Sign in</h1>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {error && <p className="text-body text-text-danger">{error}</p>}

          <Field label="Email" htmlFor="email">
            <Input
              id="email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>

          <Field label="Password" htmlFor="password">
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="pr-16"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-meta text-text-tertiary hover:text-text-secondary"
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </Field>

          <Button type="submit" className="w-full" loading={submitting} loadingText="Signing in…">
            Sign in
          </Button>
        </form>

        <p className="mt-4 text-meta text-text-tertiary">
          Forgot your password? Ask Samir to reset it.
        </p>
      </div>
    </div>
  )
}
