import { useQuery } from "@tanstack/react-query"
import { apiFetch } from "./client"

export interface UserListItem {
  id: string
  display_name: string
  is_active: boolean
}

export function useUsers() {
  return useQuery({
    queryKey: ["users"],
    queryFn: () => apiFetch<UserListItem[]>("/users"),
  })
}
