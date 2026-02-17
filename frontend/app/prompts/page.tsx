'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { FileText, Plus, Edit2, Trash2, ArrowLeft, Loader2, Paperclip } from 'lucide-react'
import Link from 'next/link'
import { promptApi } from '@/lib/api-client'
import { Prompt } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

interface PromptFormData {
  name: string
  type: string
  prompt_text: string
  supports_context?: boolean
  context_description?: string
}

const PROMPT_TYPE_OPTIONS = [
  { value: 'scene_analysis', label: 'Scene Analysis' },
  { value: 'object_identification', label: 'Object Identification' },
  { value: 'subtitling', label: 'Subtitling' },
  { value: 'key_moments', label: 'Key Moments' },
  { value: 'cliffhanger_analysis', label: 'Cliffhanger Analysis' },
  { value: 'custom', label: 'Custom' },
]

export default function PromptsPage() {
  const queryClient = useQueryClient()
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [editingPrompt, setEditingPrompt] = useState<Prompt | null>(null)
  const [deletingPrompt, setDeletingPrompt] = useState<Prompt | null>(null)
  const [formData, setFormData] = useState<PromptFormData>({
    name: '',
    type: 'scene_analysis',
    prompt_text: '',
  })
  const [formErrors, setFormErrors] = useState<Partial<PromptFormData>>({})

  const { data: prompts, isLoading } = useQuery<Prompt[]>({
    queryKey: ['prompts'],
    queryFn: () => promptApi.listPrompts(),
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
      // Show error message if prompt is in use
      alert(error.response?.data?.detail || 'Failed to delete prompt')
      setDeletingPrompt(null)
    },
  })

  const resetForm = () => {
    setFormData({
      name: '',
      type: 'scene_analysis',
      prompt_text: '',
      supports_context: false,
      context_description: ''
    })
    setFormErrors({})
  }

  const validateForm = (): boolean => {
    const errors: Partial<PromptFormData> = {}

    if (!formData.name.trim()) {
      errors.name = 'Name is required'
    } else if (formData.name.length < 3) {
      errors.name = 'Name must be at least 3 characters'
    } else if (formData.name.length > 100) {
      errors.name = 'Name must be less than 100 characters'
    }

    if (!formData.type) {
      errors.type = 'Type is required'
    }

    if (!formData.prompt_text.trim()) {
      errors.prompt_text = 'Prompt text is required'
    } else if (formData.prompt_text.length < 10) {
      errors.prompt_text = 'Prompt text must be at least 10 characters'
    } else if (formData.prompt_text.length > 50000) {
      errors.prompt_text = 'Prompt text must be less than 50,000 characters'
    }

    setFormErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleCreate = () => {
    if (!validateForm()) return
    createMutation.mutate(formData)
  }

  const handleUpdate = () => {
    if (!editingPrompt || !validateForm()) return
    updateMutation.mutate({
      promptId: editingPrompt.prompt_id,
      data: formData,
    })
  }

  const handleEdit = (prompt: Prompt) => {
    setEditingPrompt(prompt)
    setFormData({
      name: prompt.name,
      type: prompt.type,
      prompt_text: prompt.prompt_text,
      supports_context: prompt.supports_context || false,
      context_description: prompt.context_description || '',
    })
  }

  const handleDelete = (prompt: Prompt) => {
    setDeletingPrompt(prompt)
  }

  const confirmDelete = () => {
    if (deletingPrompt) {
      deleteMutation.mutate(deletingPrompt.prompt_id)
    }
  }

  const handleOpenCreateDialog = () => {
    resetForm()
    setShowCreateDialog(true)
  }

  const handleCloseCreateDialog = () => {
    setShowCreateDialog(false)
    resetForm()
  }

  const handleCloseEditDialog = () => {
    setEditingPrompt(null)
    resetForm()
  }

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8">
      {/* Page Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Prompt Management</h1>
          <p className="text-muted-foreground mt-1">Create and manage analysis prompts</p>
        </div>
        <Button onClick={handleOpenCreateDialog} size="lg">
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
              <Card key={prompt.prompt_id} className="flex flex-col">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <CardTitle className="line-clamp-1">{prompt.name}</CardTitle>
                        {prompt.supports_context && (
                          <span title="Supports context files">
                            <Paperclip className="h-4 w-4 text-blue-600" aria-label="Supports context files" />
                          </span>
                        )}
                      </div>
                      <CardDescription className="mt-1">
                        {PROMPT_TYPE_OPTIONS.find(opt => opt.value === prompt.type)?.label || prompt.type}
                        {' • '}
                        {prompt.jobs_count || 0} job(s)
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="flex-1">
                  <p className="text-sm text-muted-foreground line-clamp-3">
                    {prompt.prompt_text}
                  </p>
                  {prompt.supports_context && prompt.context_description && (
                    <p className="mt-2 text-xs text-blue-600 italic">
                      Context: {prompt.context_description}
                    </p>
                  )}
                </CardContent>
                <CardContent className="flex justify-end gap-2 border-t pt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleEdit(prompt)}
                  >
                    <Edit2 className="mr-2 h-4 w-4" />
                    Edit
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleDelete(prompt)}
                    disabled={deleteMutation.isPending}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <Card>
            <CardContent className="flex items-center justify-center py-12">
              <div className="text-center">
                <FileText className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-4 text-lg font-semibold">No prompts yet</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  Create your first prompt to start analyzing videos
                </p>
                <Button onClick={handleOpenCreateDialog} className="mt-4">
                  <Plus className="mr-2 h-4 w-4" />
                  Create Prompt
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

      {/* Create/Edit Dialog */}
      <Dialog open={showCreateDialog || editingPrompt !== null} onOpenChange={(open) => {
        if (!open) {
          if (showCreateDialog) handleCloseCreateDialog()
          if (editingPrompt) handleCloseEditDialog()
        }
      }}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editingPrompt ? 'Edit Prompt' : 'Create New Prompt'}</DialogTitle>
            <DialogDescription>
              {editingPrompt
                ? 'Update the prompt name and text. Changes will apply to new jobs only.'
                : 'Create a new prompt for scene analysis. You can use this prompt when starting new analysis jobs.'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">
                Name <span className="text-red-500">*</span>
              </Label>
              <Input
                id="name"
                placeholder="e.g., Sports Highlights Analysis"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className={formErrors.name ? 'border-red-500' : ''}
              />
              {formErrors.name && (
                <p className="text-sm text-red-500">{formErrors.name}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="type">
                Type <span className="text-red-500">*</span>
              </Label>
              <Select
                value={formData.type}
                onValueChange={(value) => setFormData({ ...formData, type: value })}
              >
                <SelectTrigger id="type" className={formErrors.type ? 'border-red-500' : ''}>
                  <SelectValue placeholder="Select type..." />
                </SelectTrigger>
                <SelectContent>
                  {PROMPT_TYPE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {formErrors.type && (
                <p className="text-sm text-red-500">{formErrors.type}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="prompt_text">
                Prompt Text <span className="text-red-500">*</span>
              </Label>
              <Textarea
                id="prompt_text"
                placeholder="Enter the prompt for scene analysis..."
                value={formData.prompt_text}
                onChange={(e) => setFormData({ ...formData, prompt_text: e.target.value })}
                rows={10}
                className={formErrors.prompt_text ? 'border-red-500' : ''}
              />
              {formErrors.prompt_text && (
                <p className="text-sm text-red-500">{formErrors.prompt_text}</p>
              )}
              <p className="text-xs text-muted-foreground">
                {formData.prompt_text.length.toLocaleString()} / 50,000 characters
              </p>
            </div>
            <div className="space-y-3 rounded-lg border p-4">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="supports_context"
                  checked={formData.supports_context}
                  onCheckedChange={(checked) =>
                    setFormData({ ...formData, supports_context: checked as boolean })
                  }
                />
                <Label
                  htmlFor="supports_context"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  Supports additional context files
                </Label>
              </div>
              {formData.supports_context && (
                <div className="space-y-2 pl-6">
                  <Label htmlFor="context_description" className="text-sm">
                    Context Description (Optional)
                  </Label>
                  <Input
                    id="context_description"
                    placeholder="e.g., Upload player statistics or team roster"
                    value={formData.context_description || ''}
                    onChange={(e) =>
                      setFormData({ ...formData, context_description: e.target.value })
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    Describe what type of context files users should upload for this prompt
                  </p>
                </div>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={editingPrompt ? handleCloseEditDialog : handleCloseCreateDialog}
            >
              Cancel
            </Button>
            <Button
              onClick={editingPrompt ? handleUpdate : handleCreate}
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              {(createMutation.isPending || updateMutation.isPending) && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {editingPrompt ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deletingPrompt !== null} onOpenChange={(open) => {
        if (!open) setDeletingPrompt(null)
      }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Prompt?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &ldquo;{deletingPrompt?.name}&rdquo;?
              {deletingPrompt && deletingPrompt.jobs_count && deletingPrompt.jobs_count > 0 ? (
                <span className="mt-2 block font-semibold text-red-600">
                  Warning: {deletingPrompt.jobs_count} job(s) are using this prompt. Deletion will be blocked.
                </span>
              ) : (
                <span className="mt-2 block">
                  This action cannot be undone.
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              disabled={deleteMutation.isPending}
              className="bg-red-600 hover:bg-red-700"
            >
              {deleteMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
