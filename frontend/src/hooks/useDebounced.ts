import { useEffect, useState } from "react"

/**
 * Trails a value by `delay` ms.
 *
 * The activity search runs server-side — it has to, because the point is
 * finding something in a history too long to have shipped to the browser.
 * Without this, typing "hypothecation" is thirteen queries, each an ILIKE
 * scan, and the last one to return wins rather than the last one typed.
 */
export function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debounced
}
