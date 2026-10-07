import { useEffect } from "react"

// DESIGN.md §6.5 gives the task page the window title
// "SHRM-12 Review term sheet – Lilkis". With a dozen deal-room tabs open
// at once, every one of them read "Lilkis Deal Room" and told you nothing.
export function useDocumentTitle(title: string | undefined): void {
  useEffect(() => {
    if (!title) return
    const previous = document.title
    document.title = `${title} – Lilkis`
    return () => {
      document.title = previous
    }
  }, [title])
}
