import { useState, useRef, useEffect } from "react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { PaperContext } from "./paper-context"
import { ChatMessage } from "./chat-message"
import { ChatInput } from "./chat-input"
import {
  MessageSquare,
  Code2,
  FlaskConical,
  History,
  Settings,
  Maximize2,
  Minimize2,
} from "lucide-react"

const API_BASE = "http://127.0.0.1:8000"

export interface NormalizedPaper {
  arxivId: string
  title: string
  authors: Array<{ name: string; affiliation: string; hasA39: boolean }>
  abstract: string
  publishedDate: string
  categories: string[]
}

interface Message {
  role: "user" | "assistant"
  content: string
}

function buildGreeting(paper: NormalizedPaper): string {
  const names = paper.authors.slice(0, 2).map((a) => a.name)
  const authorStr =
    names.length === 0
      ? "the authors"
      : names.join(" and ") + (paper.authors.length > 2 ? " et al." : "")
  return (
    `I've loaded and indexed the full text of "${paper.title}" by ${authorStr}.\n\n` +
    `I can search the paper, find related work, fetch GitHub implementations, and run sandboxed experiment code. What would you like to explore?`
  )
}

export function ExtensionSidebar({ paper }: { paper: NormalizedPaper | null }) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Reset conversation when paper changes
  useEffect(() => {
    if (paper) {
      setMessages([{ role: "assistant", content: buildGreeting(paper) }])
    } else {
      setMessages([])
    }
  }, [paper?.arxivId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isLoading])

  const handleSend = async (text: string) => {
    if (!paper || isLoading) return
    const userMsg: Message = { role: "user", content: text }
    const history = [...messages, userMsg]
    setMessages(history)
    setIsLoading(true)

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          arxivId: paper.arxivId,
          title: paper.title,
          abstract: paper.abstract,
          messages: history.map((m) => ({ role: m.role, content: m.content })),
          tools: [],
        }),
      })
      const raw = await res.text()
      let data: { reply?: string; detail?: unknown }
      try {
        data = JSON.parse(raw)
      } catch {
        throw new Error(raw.slice(0, 200) || res.statusText)
      }
      if (!res.ok) {
        const d = data.detail
        const msg =
          typeof d === "string"
            ? d
            : Array.isArray(d)
            ? (d as Array<{ msg?: string }>).map((e) => e.msg ?? JSON.stringify(e)).join("; ")
            : JSON.stringify(d)
        throw new Error(msg || res.statusText)
      }
      if (!data.reply) throw new Error("Empty response from agent")
      setMessages((prev) => [...prev, { role: "assistant", content: data.reply! }])
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setMessages((prev) => [...prev, { role: "assistant", content: `Sorry, something went wrong: ${msg}` }])
    } finally {
      setIsLoading(false)
    }
  }

  const suggestions = ["Explain the methodology", "What are the key results?", "Find related work"]

  if (!paper) {
    return (
      <div className="flex flex-col h-full bg-background border-l border-border items-center justify-center px-6">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center mb-4">
          <span className="text-sm font-bold text-white">PA</span>
        </div>
        <p className="text-sm text-muted-foreground text-center leading-relaxed">
          Navigate to an arXiv abstract page to start chatting with the paper.
        </p>
      </div>
    )
  }

  return (
    <div
      className={cn(
        "flex flex-col h-full bg-background border-l border-border transition-all duration-300",
        isExpanded ? "w-[520px]" : "w-[380px]"
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-card">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-primary to-accent flex items-center justify-center">
            <span className="text-xs font-bold text-white">PA</span>
          </div>
          <div>
            <h1 className="text-sm font-semibold text-foreground">PaperAgent</h1>
            <p className="text-[10px] text-muted-foreground">arxiv.org active</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-foreground"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-foreground"
          >
            <Settings className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Paper metadata */}
      <PaperContext {...paper} />

      {/* Tabs */}
      <Tabs defaultValue="chat" className="flex-1 flex flex-col overflow-hidden">
        <TabsList className="grid grid-cols-4 mx-3 mt-2 bg-secondary/50 h-9">
          <TabsTrigger value="chat" className="text-xs gap-1.5 data-[state=active]:bg-background">
            <MessageSquare className="w-3.5 h-3.5" />
            Chat
          </TabsTrigger>
          <TabsTrigger value="code" className="text-xs gap-1.5 data-[state=active]:bg-background">
            <Code2 className="w-3.5 h-3.5" />
            Code
          </TabsTrigger>
          <TabsTrigger value="experiments" className="text-xs gap-1.5 data-[state=active]:bg-background">
            <FlaskConical className="w-3.5 h-3.5" />
            Runs
          </TabsTrigger>
          <TabsTrigger value="history" className="text-xs gap-1.5 data-[state=active]:bg-background">
            <History className="w-3.5 h-3.5" />
            History
          </TabsTrigger>
        </TabsList>

        <TabsContent
          value="chat"
          className="flex-1 flex flex-col overflow-hidden mt-0 data-[state=active]:flex"
        >
          <div className="flex-1 overflow-y-auto px-4 py-2">
            {messages.map((msg, i) => (
              <ChatMessage key={i} role={msg.role} content={msg.content} />
            ))}
            {isLoading && (
              <ChatMessage
                role="assistant"
                content="Analyzing your request and calling tools…"
                isStreaming
              />
            )}
            <div ref={messagesEndRef} />
          </div>
          <ChatInput
            onSend={handleSend}
            isLoading={isLoading}
            suggestions={messages.length <= 1 ? suggestions : undefined}
          />
        </TabsContent>

        <TabsContent value="code" className="flex-1 overflow-y-auto p-4 mt-0">
          <div className="rounded-lg border border-border bg-secondary/30 p-4">
            <p className="text-sm text-muted-foreground">
              Code execution environment ready. Start a conversation to generate and run code.
            </p>
          </div>
        </TabsContent>

        <TabsContent value="experiments" className="flex-1 overflow-y-auto p-4 mt-0">
          <div className="rounded-lg border border-border bg-secondary/30 p-4">
            <p className="text-sm text-muted-foreground">
              No experiment runs yet. Ask me to replicate results from the paper.
            </p>
          </div>
        </TabsContent>

        <TabsContent value="history" className="flex-1 overflow-y-auto p-4 mt-0">
          <div className="rounded-lg border border-border bg-secondary/30 p-4">
            <p className="text-sm text-muted-foreground">Session history will appear here.</p>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
