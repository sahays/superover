import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { FileText, Plus, Loader2 } from 'lucide-react'
import { promptApi } from '@/lib/api-client'
import { Prompt, CategorySchema } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { PROMPT_TYPE_OPTIONS } from '@/lib/prompt-constants'
import { usePromptForm, type PromptFormData } from '@/hooks/use-prompt-form'
import { useSchemaEditor } from '@/hooks/use-schema-editor'
import { PromptCard } from '@/components/prompts/prompt-card'
import { CategorySchemaCard } from '@/components/prompts/category-schema-card'
import { SchemaEditDialog } from '@/components/prompts/schema-edit-dialog'
import { PromptFormDialog } from '@/components/prompts/prompt-form-dialog'
import { PromptDeleteDialog } from '@/components/prompts/prompt-delete-dialog'

export default function PromptsPage() {
  const queryClient = useQueryClient()
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [editingPrompt, setEditingPrompt] = useState<Prompt | null>(null)
  const [deletingPrompt, setDeletingPrompt] = useState<Prompt | null>(null)

  const { formData, setFormData, formErrors, resetForm, populateFrom, validateForm } = usePromptForm()
  const schemaEditor = useSchemaEditor()

  const { data: prompts, isLoading } = useQuery<Prompt[]>({
    queryKey: ['prompts'],
    queryFn: () => promptApi.listPrompts(),
  })

  const { data: categorySchemas } = useQuery<CategorySchema[]>({
    queryKey: ['categorySchemas'],
    queryFn: () => promptApi.listSchemas(),
  })

  const createMutation = useMutation({
    mutationFn: (data: PromptFormData) => promptApi.createPrompt(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      setShowCreateDialog(false)
      resetForm()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ promptId, data }: { promptId: string; data: Partial<PromptFormData> }) =>
      promptApi.updatePrompt(promptId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      setEditingPrompt(null)
      resetForm()
    },
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
    mutationFn: ({ category, response_schema }: { category: string; response_schema: Record<string, unknown> | null }) =>
      promptApi.setSchema(category, { response_schema }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categorySchemas'] })
      schemaEditor.closeEditor()
    },
  })

  const handleCreate = () => {
    if (!validateForm()) return
    createMutation.mutate(formData)
  }

  const handleUpdate = () => {
    if (!editingPrompt || !validateForm()) return
    updateMutation.mutate({ promptId: editingPrompt.prompt_id, data: formData })
  }

  const handleEdit = (prompt: Prompt) => {
    setEditingPrompt(prompt)
    populateFrom(prompt)
  }

  const handleSaveSchema = () => {
    if (!schemaEditor.editingCategory) return
    const result = schemaEditor.parseSchema()
    if (result.valid) {
      setSchemaMutation.mutate({ category: schemaEditor.editingCategory, response_schema: result.schema })
    }
  }

  const handleClearSchema = () => {
    if (!schemaEditor.editingCategory) return
    setSchemaMutation.mutate({ category: schemaEditor.editingCategory, response_schema: null })
  }

  const getSchemaForCategory = (category: string) =>
    categorySchemas?.find(s => s.category === category)

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold font-heading">Prompt Management</h1>
          <p className="text-muted-foreground mt-1">Create and manage analysis prompts</p>
        </div>
        <Button onClick={() => { resetForm(); setShowCreateDialog(true) }} size="lg">
          <Plus className="mr-2 h-4 w-4" />
          Create Prompt
        </Button>
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
              onEdit={handleEdit}
              onDelete={setDeletingPrompt}
              isDeleting={deleteMutation.isPending}
            />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="flex items-center justify-center py-12">
            <div className="text-center">
              <FileText className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-4 text-lg font-semibold">No prompts yet</h3>
              <p className="mt-2 text-sm text-muted-foreground">Create your first prompt to start analyzing videos</p>
              <Button onClick={() => { resetForm(); setShowCreateDialog(true) }} className="mt-4">
                <Plus className="mr-2 h-4 w-4" />
                Create Prompt
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Category Schemas Section */}
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
              hasSchema={getSchemaForCategory(option.value)?.response_schema != null}
              onEditSchema={(cat) => schemaEditor.openEditor(cat, categorySchemas)}
            />
          ))}
        </div>
      </div>

      <SchemaEditDialog
        editingCategory={schemaEditor.editingCategory}
        schemaText={schemaEditor.schemaText}
        onSchemaTextChange={schemaEditor.setSchemaText}
        schemaError={schemaEditor.schemaError}
        onSchemaErrorClear={() => schemaEditor.setSchemaError(null)}
        onSave={handleSaveSchema}
        onClear={handleClearSchema}
        onClose={schemaEditor.closeEditor}
        isSaving={setSchemaMutation.isPending}
      />

      <PromptFormDialog
        open={showCreateDialog || editingPrompt !== null}
        isEditing={editingPrompt !== null}
        formData={formData}
        formErrors={formErrors}
        onFormChange={setFormData}
        onSubmit={editingPrompt ? handleUpdate : handleCreate}
        onClose={() => {
          setShowCreateDialog(false)
          setEditingPrompt(null)
          resetForm()
        }}
        isSaving={createMutation.isPending || updateMutation.isPending}
      />

      <PromptDeleteDialog
        prompt={deletingPrompt}
        onConfirm={() => deletingPrompt && deleteMutation.mutate(deletingPrompt.prompt_id)}
        onCancel={() => setDeletingPrompt(null)}
        isDeleting={deleteMutation.isPending}
      />
    </div>
  )
}
