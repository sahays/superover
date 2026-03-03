import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface SearchResultCardProps {
  text: string
  score: number
  timestamp?: string | null
  chunkIndex?: number | null
  onClick?: () => void
}

export function SearchResultCard({
  text,
  timestamp,
  chunkIndex,
  onClick,
}: SearchResultCardProps) {
  return (
    <Card
      className={onClick ? 'cursor-pointer transition-colors hover:bg-muted/50' : ''}
      onClick={onClick}
    >
      <CardContent className="p-4">
        <div className="flex-1 min-w-0">
          {(timestamp || chunkIndex != null) && (
            <div className="flex items-center gap-2 mb-2">
              {timestamp && (
                <Badge variant="outline" className="text-xs">
                  {timestamp}
                </Badge>
              )}
              {chunkIndex != null && (
                <Badge variant="secondary" className="text-xs">
                  Chunk {chunkIndex}
                </Badge>
              )}
            </div>
          )}
          <p className="text-sm text-muted-foreground line-clamp-3">{text}</p>
        </div>
      </CardContent>
    </Card>
  )
}
