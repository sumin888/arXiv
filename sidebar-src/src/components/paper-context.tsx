import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { FileText, Users, Calendar, ExternalLink } from "lucide-react"

interface Author {
  name: string
  affiliation: string
  hasA39: boolean
}

interface PaperContextProps {
  title: string
  authors: Author[]
  arxivId: string
  publishedDate: string
  categories: string[]
}

export function PaperContext({
  title,
  authors,
  arxivId,
  publishedDate,
  categories,
}: PaperContextProps) {
  return (
    <div className="p-4 border-b border-border">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
          <FileText className="w-5 h-5 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="text-sm font-semibold text-foreground leading-tight line-clamp-2">
            {title}
          </h2>
          <div className="flex items-center gap-2 mt-1.5 text-xs text-muted-foreground flex-wrap">
            {publishedDate && (
              <span className="flex items-center gap-1">
                <Calendar className="w-3 h-3" />
                {publishedDate}
              </span>
            )}
            <span className="flex items-center gap-1">
              <ExternalLink className="w-3 h-3" />
              {arxivId}
            </span>
          </div>
        </div>
      </div>

      {categories.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {categories.map((cat) => (
            <Badge key={cat} variant="secondary" className="text-xs px-2 py-0.5">
              {cat}
            </Badge>
          ))}
        </div>
      )}

      {authors.length > 0 && (
        <div className="mt-3">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-2">
            <Users className="w-3 h-3" />
            <span>Authors</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {authors.slice(0, 6).map((author) => (
              <div
                key={author.name}
                className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-secondary/50 border border-border/50"
              >
                <Avatar className="w-5 h-5">
                  <AvatarFallback className="text-[10px] bg-primary/20 text-primary">
                    {author.name
                      .split(" ")
                      .map((n) => n[0])
                      .join("")}
                  </AvatarFallback>
                </Avatar>
                <span className="text-xs text-foreground">{author.name}</span>
                {author.hasA39 && (
                  <Badge className="text-[9px] px-1 py-0 h-4 bg-accent text-accent-foreground">
                    a39
                  </Badge>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
