import { cn } from "@/lib/utils"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { ToolExecutionGroup, type ToolType, type ToolStatus } from "./tool-execution"
import { Bot, User } from "lucide-react"

interface Tool {
  type: ToolType
  name: string
  status: ToolStatus
  duration?: string
  details?: string
  output?: string
}

interface ChatMessageProps {
  role: "user" | "assistant"
  content: string
  tools?: Tool[]
  isStreaming?: boolean
}

export function ChatMessage({ role, content, tools, isStreaming }: ChatMessageProps) {
  const isUser = role === "user"

  return (
    <div className={cn("flex gap-3 py-4", isUser ? "flex-row-reverse" : "flex-row")}>
      <Avatar
        className={cn("w-8 h-8 flex-shrink-0", isUser ? "bg-secondary" : "bg-primary/20")}
      >
        <AvatarFallback
          className={isUser ? "bg-secondary text-foreground" : "bg-primary/20 text-primary"}
        >
          {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
        </AvatarFallback>
      </Avatar>

      <div className={cn("flex-1 space-y-2", isUser ? "text-right" : "text-left")}>
        {isUser ? (
          <div className="inline-block rounded-2xl rounded-tr-sm bg-primary text-primary-foreground px-4 py-2.5 text-sm">
            {content}
          </div>
        ) : (
          <div className="space-y-2">
            {tools && tools.length > 0 && <ToolExecutionGroup tools={tools} />}
            <div
              className={cn(
                "text-sm text-foreground leading-relaxed whitespace-pre-wrap",
                isStreaming && "after:content-['▋'] after:ml-0.5 after:animate-pulse"
              )}
            >
              {content}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
