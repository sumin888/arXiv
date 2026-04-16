import { useEffect, useState } from "react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Bot } from "lucide-react"

const STAGES = [
  "Reading the paper…",
  "Searching relevant sections…",
  "Calling tools…",
  "Generating response…",
]

export function ThinkingIndicator() {
  const [stageIndex, setStageIndex] = useState(0)

  useEffect(() => {
    const id = setInterval(() => {
      setStageIndex((i) => (i + 1) % STAGES.length)
    }, 2000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="flex gap-3 py-4">
      <Avatar className="w-8 h-8 flex-shrink-0 bg-primary/20">
        <AvatarFallback className="bg-primary/20 text-primary">
          <Bot className="w-4 h-4" />
        </AvatarFallback>
      </Avatar>

      <div className="flex flex-col gap-1.5 justify-center">
        {/* Bouncing dots */}
        <div className="flex items-center gap-1">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="w-2 h-2 rounded-full bg-primary/60"
              style={{
                animation: "bounce 1.2s infinite ease-in-out",
                animationDelay: `${i * 0.2}s`,
              }}
            />
          ))}
        </div>
        {/* Cycling status text */}
        <p className="text-xs text-muted-foreground transition-all duration-500">
          {STAGES[stageIndex]}
        </p>
      </div>

      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.5; }
          40%            { transform: translateY(-6px); opacity: 1; }
        }
      `}</style>
    </div>
  )
}
