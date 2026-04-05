import { useState, useEffect } from "react"
import { ExtensionSidebar, type NormalizedPaper } from "./components/extension-sidebar"

// Raw shape sent by content/content.js
interface RawPaper {
  arxivId: string
  title: string
  authors: string[]
  abstract: string
  subjects?: string   // e.g. "cs.CL; cs.LG; stat.ML"
  dateText?: string   // e.g. "[Submitted on 12 Jun 2017]"
  url?: string
}

function normalizePaper(raw: RawPaper): NormalizedPaper {
  const categories = raw.subjects
    ? raw.subjects
        .split(/[;,]/)
        .map((s) => s.trim())
        .filter(Boolean)
        .slice(0, 4)
    : []

  // Strip brackets/prefix from "[Submitted on 12 Jun 2017 (v1), ...]"
  const publishedDate = raw.dateText
    ? raw.dateText.replace(/^\[?submitted on\s*/i, "").replace(/\s*\(.*$/, "").replace(/\]$/, "").trim()
    : ""

  const authors = (raw.authors || []).map((name) => ({
    name,
    affiliation: "",
    hasA39: false,
  }))

  return {
    arxivId: raw.arxivId,
    title: raw.title || raw.arxivId,
    authors,
    abstract: raw.abstract || "",
    publishedDate,
    categories,
  }
}

export function App() {
  const [paper, setPaper] = useState<NormalizedPaper | null>(null)

  useEffect(() => {
    // Load paper already in session storage (sidebar opened after navigation)
    chrome.storage.session.get("currentPaper", ({ currentPaper }) => {
      if (currentPaper) setPaper(normalizePaper(currentPaper as RawPaper))
    })

    // Live update from background worker when user navigates
    const listener = (message: { type: string; paper: RawPaper }) => {
      if (message.type === "PAPER_UPDATED") {
        setPaper(normalizePaper(message.paper))
      }
    }
    chrome.runtime.onMessage.addListener(listener)
    return () => chrome.runtime.onMessage.removeListener(listener)
  }, [])

  return <ExtensionSidebar paper={paper} />
}
