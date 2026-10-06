# Frontend AGENTS.md — Lilkis Deal Room

Root context: /CLAUDE.md
Design spec: /DESIGN.md
PRD: /PRD.md

## Stack
React 18, TypeScript 5 strict, Vite 5, Tailwind 3, shadcn/ui, TanStack Query 5, React Router 6, react-hook-form + zod, lucide-react

## Key rules
- All API calls through src/api/client.ts (credentials: include)
- TanStack Query for all server state; Zustand for auth state only
- No inline styles; Tailwind only
- No string literals in JSX; use copy.ts
- Chunked upload via src/hooks/useUpload.ts
- TypeScript strict; no any, no !
- Design tokens (colors, type scale, spacing, radius) come from DESIGN.md §3 — they live in tailwind.config.ts / CSS variables, not ad hoc values in components.

## Running
```
pnpm install
pnpm dev          # dev server
pnpm build        # production build
pnpm tsc --noEmit # type check
pnpm eslint src/
```
