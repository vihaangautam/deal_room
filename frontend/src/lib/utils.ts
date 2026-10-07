import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

// DESIGN.md §7: "15 Oct 2026" — store UTC, display IST (PRD §10).
export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  }).format(new Date(iso))
}

export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  }).format(new Date(iso))
}

// DESIGN.md §7: "1.4 GB" — binary units, one decimal place above 1 KB.
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ["KB", "MB", "GB"]
  let value = bytes / 1024
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`
}

// DESIGN.md §7: Indian digit grouping above 1,000.
export function formatNumber(n: number): string {
  return new Intl.NumberFormat("en-IN").format(n)
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/)
  const first = parts[0]?.[0] ?? ""
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : ""
  return (first + last).toUpperCase()
}

// DESIGN.md §3.1 — six muted avatar tints, picked by hashing the user id.
const AVATAR_TINTS = ["#E5F4E1", "#E8F0FA", "#FDF3DC", "#F3EFEA", "#EEF0EE", "#EDEBF3"]

export function avatarColor(userId: string): string {
  let hash = 0
  for (let i = 0; i < userId.length; i += 1) {
    hash = (hash * 31 + userId.charCodeAt(i)) >>> 0
  }
  return AVATAR_TINTS[hash % AVATAR_TINTS.length] ?? "#EEF0EE"
}
