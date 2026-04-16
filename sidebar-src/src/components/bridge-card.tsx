import { Sparkles, X } from "lucide-react"
import { Button } from "@/components/ui/button"

export interface BridgeData {
  arxivId: string
  content: string    // text inside the <bridge> tag
}

interface BridgeCardProps {
  bridge: BridgeData
  onExplore: (bridge: BridgeData) => void
  onDismiss: () => void
}

export function BridgeCard({ bridge, onExplore, onDismiss }: BridgeCardProps) {
  return (
    <div className="mt-3 rounded-xl border border-primary/25 bg-primary/5 px-4 py-3 text-sm">
      <div className="flex items-start gap-2">
        <Sparkles className="w-3.5 h-3.5 text-primary mt-0.5 flex-shrink-0" />
        <p className="flex-1 text-foreground/80 leading-relaxed whitespace-pre-wrap text-[13px]">
          {bridge.content}
        </p>
      </div>
      <div className="flex items-center gap-2 mt-3">
        <Button
          size="sm"
          variant="outline"
          className="h-7 text-xs border-primary/30 text-primary hover:bg-primary/10 hover:text-primary"
          onClick={() => onExplore(bridge)}
        >
          Explore this →
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="h-7 text-xs text-muted-foreground hover:text-foreground"
          onClick={onDismiss}
        >
          <X className="w-3 h-3 mr-1" />
          Dismiss
        </Button>
      </div>
    </div>
  )
}

/**
 * Parse a <bridge arxiv_id="...">...</bridge> tag out of an assistant response.
 * Returns the stripped main text and the extracted bridge data (or null).
 */
export function parseBridgeTag(text: string): {
  main: string
  bridge: BridgeData | null
} {
  const match = text.match(/<bridge\s+arxiv_id="([^"]+)">([\s\S]*?)<\/bridge>/i)
  if (!match) return { main: text, bridge: null }

  const arxivId = match[1].trim()
  const content = match[2].trim()
  const main = text.replace(match[0], "").trim()

  return { main, bridge: { arxivId, content } }
}
