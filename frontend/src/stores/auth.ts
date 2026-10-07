import { create } from "zustand"
import type { User } from "@/api/types"

// CLAUDE.md §6.2: Zustand for auth state only — everything else is
// TanStack Query. "status" starts "loading" so routes can wait for the
// initial /auth/me call (done in App.tsx) before deciding to redirect.
interface AuthState {
  user: User | null
  status: "loading" | "authenticated" | "anonymous"
  setUser: (user: User) => void
  clear: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  status: "loading",
  setUser: (user) => set({ user, status: "authenticated" }),
  clear: () => set({ user: null, status: "anonymous" }),
}))
