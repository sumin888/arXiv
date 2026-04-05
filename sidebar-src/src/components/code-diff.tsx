import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { TrendingUp, TrendingDown, Minus } from "lucide-react"

interface MetricDiff {
  name: string
  reported: number
  replicated: number
  unit?: string
}

interface CodeDiffProps {
  title: string
  metrics: MetricDiff[]
}

export function CodeDiff({ title, metrics }: CodeDiffProps) {
  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden my-3">
      <div className="px-3 py-2 border-b border-border bg-secondary/30">
        <span className="text-xs font-medium text-foreground">{title}</span>
      </div>
      <div className="p-3 space-y-2">
        {metrics.map((metric) => {
          const diff = metric.replicated - metric.reported
          const percentDiff = ((diff / metric.reported) * 100).toFixed(1)
          const isPositive = diff > 0
          const isNeutral = Math.abs(diff) < 0.01

          return (
            <div
              key={metric.name}
              className="flex items-center justify-between py-1.5 px-2 rounded-md bg-secondary/30"
            >
              <span className="text-xs text-muted-foreground">{metric.name}</span>
              <div className="flex items-center gap-3">
                <div className="text-xs">
                  <span className="text-muted-foreground">Reported: </span>
                  <span className="text-foreground font-mono">
                    {metric.reported.toFixed(2)}
                    {metric.unit}
                  </span>
                </div>
                <div className="text-xs">
                  <span className="text-muted-foreground">Replicated: </span>
                  <span className="text-foreground font-mono">
                    {metric.replicated.toFixed(2)}
                    {metric.unit}
                  </span>
                </div>
                <Badge
                  variant="secondary"
                  className={cn(
                    "text-[10px] px-1.5 py-0 h-5 font-mono",
                    isNeutral
                      ? "bg-muted text-muted-foreground"
                      : isPositive
                      ? "bg-accent/20 text-accent"
                      : "bg-destructive/20 text-destructive"
                  )}
                >
                  {isNeutral ? (
                    <Minus className="w-3 h-3 mr-0.5" />
                  ) : isPositive ? (
                    <TrendingUp className="w-3 h-3 mr-0.5" />
                  ) : (
                    <TrendingDown className="w-3 h-3 mr-0.5" />
                  )}
                  {isNeutral ? "0%" : `${isPositive ? "+" : ""}${percentDiff}%`}
                </Badge>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
