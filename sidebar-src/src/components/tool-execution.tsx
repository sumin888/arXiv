import { useState } from "react"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import {
  ChevronDown,
  ChevronRight,
  Search,
  Code,
  GitBranch,
  Database,
  CheckCircle2,
  Loader2,
  AlertCircle,
  Sparkles,
} from "lucide-react"

export type ToolType = "rag" | "code" | "github" | "toolUniverse" | "a39"
export type ToolStatus = "running" | "complete" | "error"

interface ToolExecutionProps {
  type: ToolType
  name: string
  status: ToolStatus
  duration?: string
  details?: string
  output?: string
}

const toolConfig: Record<ToolType, { icon: React.ElementType; label: string; color: string }> = {
  rag: { icon: Search, label: "RAG Search", color: "text-primary" },
  code: { icon: Code, label: "Code Execution", color: "text-accent" },
  github: { icon: GitBranch, label: "GitHub", color: "text-chart-3" },
  toolUniverse: { icon: Database, label: "ToolUniverse", color: "text-chart-4" },
  a39: { icon: Sparkles, label: "Authors39", color: "text-chart-2" },
}

const statusConfig: Record<ToolStatus, { icon: React.ElementType; className: string }> = {
  running: { icon: Loader2, className: "animate-spin text-primary" },
  complete: { icon: CheckCircle2, className: "text-accent" },
  error: { icon: AlertCircle, className: "text-destructive" },
}

export function ToolExecution({
  type,
  name,
  status,
  duration,
  details,
  output,
}: ToolExecutionProps) {
  const [expanded, setExpanded] = useState(false)
  const tool = toolConfig[type]
  const statusInfo = statusConfig[status]
  const ToolIcon = tool.icon
  const StatusIcon = statusInfo.icon

  return (
    <div className="rounded-lg border border-border/50 bg-secondary/30 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 p-2.5 hover:bg-secondary/50 transition-colors"
      >
        <div className="flex-shrink-0">
          {expanded ? (
            <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
          )}
        </div>
        <div className={cn("flex-shrink-0", tool.color)}>
          <ToolIcon className="w-4 h-4" />
        </div>
        <div className="flex-1 text-left">
          <span className="text-xs font-medium text-foreground">{name}</span>
          {details && (
            <span className="text-xs text-muted-foreground ml-1.5 truncate">— {details}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {duration && status === "complete" && (
            <span className="text-[10px] text-muted-foreground">{duration}</span>
          )}
          <StatusIcon className={cn("w-3.5 h-3.5", statusInfo.className)} />
        </div>
      </button>

      {expanded && output && (
        <div className="px-3 pb-3 pt-1">
          <div className="rounded-md bg-background/50 p-2.5 font-mono text-xs text-muted-foreground overflow-x-auto">
            <pre className="whitespace-pre-wrap">{output}</pre>
          </div>
        </div>
      )}
    </div>
  )
}

interface ToolExecutionGroupProps {
  tools: ToolExecutionProps[]
}

export function ToolExecutionGroup({ tools }: ToolExecutionGroupProps) {
  return (
    <div className="space-y-1.5 my-3">
      {tools.map((tool, i) => (
        <ToolExecution key={i} {...tool} />
      ))}
    </div>
  )
}
