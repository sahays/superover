import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { FileText, Plus, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { promptApi } from '@/lib/api-client'
import { Prompt, CategorySchema } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { PROMPT_TYPE_OPTIONS } from '@/lib/prompt-constants'
import { useSchemaEditor } from '@/hooks/use-schema-editor'
import { useAuthStore } from '@/store/useAuthStore'
import { PromptCard } from '@/components/prompts/prompt-card'
import { CategorySchemaCard } from '@/components/prompts/category-schema-card'
import { SchemaEditDialog } from '@/components/prompts/schema-edit-dialog'
import { PromptDeleteDialog } from '@/components/prompts/prompt-delete-dialog'
import { useState } from 'react'

export default function PromptsPage() {
  const queryClient = useQueryClient()
  const { isMaster } = useAuthStore()
  const [deletingPrompt, setDeletingPrompt] = useState<Prompt | null>(null)
  const schemaEditor = useSchemaEditor()

  const { data: prompts, isLoading } = useQuery<Prompt[]>({
    queryKey: ['prompts'],
    queryFn: () => promptApi.listPrompts(),
  })

  const { data: categorySchemas } = useQuery<CategorySchema[]>({
    queryKey: ['categorySchemas'],
    queryFn: () => promptApi.listSchemas(),
  })

  const deleteMutation = useMutation({
    mutationFn: (promptId: string) => promptApi.deletePrompt(promptId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      setDeletingPrompt(null)
    },
    onError: (error: any) => {
      alert(error.response?.data?.detail || 'Failed to delete prompt')
      setDeletingPrompt(null)
    },
  })

  const setSchemaMutation = useMutation({
    mutationFn: ({ category, schema_name, response_schema }: { category: string; schema_name: string; response_schema: Record<string, unknown> | null }) =>
      promptApi.setSchema(category, { schema_name, response_schema }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categorySchemas'] })
      schemaEditor.closeEditor()
    },
  })

  const handleSaveSchema = () => {
    if (!schemaEditor.editingCategory) return
    const result = schemaEditor.parseSchema()
    if (result.valid) {
      setSchemaMutation.mutate({
        category: schemaEditor.editingCategory,
        schema_name: schemaEditor.editingSchemaName,
        response_schema: result.schema,
      })
    }
  }

  const handleClearSchema = () => {
    if (!schemaEditor.editingCategory) return
    promptApi.deleteSchema(schemaEditor.editingCategory, schemaEditor.editingSchemaName)
      .then(() => {
        queryClient.invalidateQueries({ queryKey: ['categorySchemas'] })
        schemaEditor.closeEditor()
      })
  }

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold font-heading">Prompts</h1>
          <p className="text-muted-foreground mt-1">Analysis prompts for scene processing</p>
        </div>
        {isMaster && (
          <Button asChild size="lg">
            <Link to="/prompts/new">
              <Plus className="mr-2 h-4 w-4" />
              Create Prompt
            </Link>
          </Button>
        )}
      </div>

      {isLoading ? (
        <Card>
          <CardContent className="flex items-center justify-center py-12">
            <div className="text-center">
              <Loader2 className="mx-auto h-12 w-12 animate-spin text-primary" />
              <p className="mt-4 text-sm text-muted-foreground">Loading prompts...</p>
            </div>
          </CardContent>
        </Card>
      ) : prompts && prompts.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {prompts.map((prompt) => (
            <PromptCard
              key={prompt.prompt_id}
              prompt={prompt}
              onDelete={isMaster ? setDeletingPrompt : undefined}
              isDeleting={deleteMutation.isPending}
              showActions={isMaster}
            />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="flex items-center justify-center py-12">
            <div className="text-center">
              <FileText className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-4 text-lg font-semibold">No prompts yet</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                {isMaster ? 'Create your first prompt to start analyzing videos' : 'No prompts have been created yet'}
              </p>
              {isMaster && (
                <Button asChild className="mt-4">
                  <Link to="/prompts/new">
                    <Plus className="mr-2 h-4 w-4" />
                    Create Prompt
                  </Link>
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Category Schemas Section — master only */}
      {isMaster && (
        <div className="mt-12">
          <h2 className="text-2xl font-bold font-heading mb-2">Category Schemas</h2>
          <p className="text-muted-foreground mb-6">
            Define JSON response schemas per prompt category. Categories with a schema get structured Gemini output; others get free text.
          </p>
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {PROMPT_TYPE_OPTIONS.map((option) => (
              <CategorySchemaCard
                key={option.value}
                label={option.label}
                value={option.value}
                schemas={categorySchemas || []}
                onEditSchema={(cat, schemaName) => schemaEditor.openEditor(cat, categorySchemas, schemaName)}
              />
            ))}
          </div>
        </div>
      )}

      {isMaster && (
        <>
          <SchemaEditDialog
            editingCategory={schemaEditor.editingCategory}
            schemaName={schemaEditor.editingSchemaName}
            onSchemaNameChange={schemaEditor.setEditingSchemaName}
            schemaText={schemaEditor.schemaText}
            onSchemaTextChange={schemaEditor.setSchemaText}
            schemaError={schemaEditor.schemaError}
            onSchemaErrorClear={() => schemaEditor.setSchemaError(null)}
            onSave={handleSaveSchema}
            onClear={handleClearSchema}
            onClose={schemaEditor.closeEditor}
            isSaving={setSchemaMutation.isPending}
          />

          <PromptDeleteDialog
            prompt={deletingPrompt}
            onConfirm={() => deletingPrompt && deleteMutation.mutate(deletingPrompt.prompt_id)}
            onCancel={() => setDeletingPrompt(null)}
            isDeleting={deleteMutation.isPending}
          />
        </>
      )}
    </div>
  )
}
