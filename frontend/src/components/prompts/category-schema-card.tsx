import { Braces } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

interface CategorySchemaCardProps {
  label: string
  value: string
  hasSchema: boolean
  onEditSchema: (category: string) => void
}

export function CategorySchemaCard({ label, value, hasSchema, onEditSchema }: CategorySchemaCardProps) {
  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{label}</CardTitle>
          <Badge variant={hasSchema ? 'default' : 'secondary'}>
            {hasSchema ? 'Structured' : 'Free Text'}
          </Badge>
        </div>
        <CardDescription className="text-xs">{value}</CardDescription>
      </CardHeader>
      <CardContent className="flex justify-end gap-2 pt-0">
        <Button variant="outline" size="sm" onClick={() => onEditSchema(value)}>
          <Braces className="mr-2 h-4 w-4" />
          Edit Schema
        </Button>
      </CardContent>
    </Card>
  )
}
