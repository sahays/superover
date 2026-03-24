import { Braces, Plus } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { CategorySchema } from '@/lib/types'

interface CategorySchemaCardProps {
  label: string
  value: string
  schemas: CategorySchema[]
  onEditSchema: (category: string, schemaName?: string) => void
}

export function CategorySchemaCard({ label, value, schemas, onEditSchema }: CategorySchemaCardProps) {
  const categorySchemas = schemas.filter(s => s.category === value)

  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{label}</CardTitle>
          <Badge variant={categorySchemas.length > 0 ? 'default' : 'secondary'}>
            {categorySchemas.length > 0 ? `${categorySchemas.length} schema(s)` : 'Free Text'}
          </Badge>
        </div>
        <CardDescription className="text-xs">{value}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 pt-0">
        {categorySchemas.map((schema) => (
          <div key={`${schema.category}__${schema.schema_name}`} className="flex items-center justify-between">
            <span className="text-sm font-mono text-muted-foreground">{schema.schema_name}</span>
            <Button variant="outline" size="sm" onClick={() => onEditSchema(value, schema.schema_name)}>
              <Braces className="mr-2 h-3 w-3" />
              Edit
            </Button>
          </div>
        ))}
        <Button variant="ghost" size="sm" className="w-full" onClick={() => onEditSchema(value)}>
          <Plus className="mr-2 h-3 w-3" />
          {categorySchemas.length > 0 ? 'Add Schema Variant' : 'Add Schema'}
        </Button>
      </CardContent>
    </Card>
  )
}
