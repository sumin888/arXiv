import { useState, useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { Send, Paperclip, Sparkles, StopCircle } from "lucide-react"

interface ChatInputProps {
  onSend: (message: string) => void
  isLoading?: boolean
  onStop?: () => void
  suggestions?: string[]
}

export function ChatInput({ onSend, isLoading, onStop, suggestions }: ChatInputProps) {
  const [value, setValue] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`
    }
  }, [value])

  const handleSubmit = () => {
    if (value.trim() && !isLoading) {
      onSend(value.trim())
      setValue("")
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="p-3 border-t border-border bg-card/50">
      {suggestions && suggestions.length > 0 && !value && (
        <div className="flex flex-wrap gap-1.5 mb-2.5">
          {suggestions.map((suggestion, i) => (
            <button
              key={i}
              onClick={() => setValue(suggestion)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs bg-secondary/70 text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors border border-border/50"
            >
              <Sparkles className="w-3 h-3" />
              {suggestion}
            </button>
          ))}
        </div>
      )}

      <div className="relative flex items-end gap-2 rounded-xl bg-secondary/50 border border-border/50 p-2 focus-within:border-primary/50 transition-colors">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 flex-shrink-0 text-muted-foreground hover:text-foreground"
        >
          <Paperclip className="w-4 h-4" />
        </Button>

        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about this paper…"
          rows={1}
          className="flex-1 bg-transparent resize-none border-0 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none min-h-[32px] py-1.5"
        />

        {isLoading ? (
          <Button
            onClick={onStop}
            size="icon"
            variant="ghost"
            className="h-8 w-8 flex-shrink-0 text-destructive hover:text-destructive hover:bg-destructive/10"
          >
            <StopCircle className="w-4 h-4" />
          </Button>
        ) : (
          <Button
            onClick={handleSubmit}
            size="icon"
            disabled={!value.trim()}
            className={cn(
              "h-8 w-8 flex-shrink-0 rounded-lg transition-all",
              value.trim()
                ? "bg-primary text-primary-foreground hover:bg-primary/90"
                : "bg-secondary text-muted-foreground"
            )}
          >
            <Send className="w-4 h-4" />
          </Button>
        )}
      </div>

      <p className="text-[10px] text-muted-foreground text-center mt-2">
        Powered by RAG, ToolUniverse, and Authors39 integration
      </p>
    </div>
  )
}
