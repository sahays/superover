import { useState, useCallback } from 'react'
import type { CategorySchema } from '@/lib/types'

export function useSchemaEditor() {
  const [editingCategory, setEditingCategory] = useState<string | null>(null)
  const [schemaText, setSchemaText] = useState('')
  const [schemaError, setSchemaError] = useState<string | null>(null)

  const openEditor = useCallback((category: string, schemas?: CategorySchema[]) => {
    const existing = schemas?.find(s => s.category === category)
    setEditingCategory(category)
    setSchemaText(existing?.response_schema ? JSON.stringify(existing.response_schema, null, 2) : '')
    setSchemaError(null)
  }, [])

  const closeEditor = useCallback(() => {
    setEditingCategory(null)
    setSchemaText('')
    setSchemaError(null)
  }, [])

  const parseSchema = useCallback((): { valid: true; schema: Record<string, unknown> | null } | { valid: false } => {
    if (!schemaText.trim()) {
      return { valid: true, schema: null }
    }
    try {
      const parsed = JSON.parse(schemaText)
      return { valid: true, schema: parsed }
    } catch {
      setSchemaError('Invalid JSON. Please check your schema syntax.')
      return { valid: false }
    }
  }, [schemaText])

  return {
    editingCategory,
    schemaText,
    setSchemaText,
    schemaError,
    setSchemaError,
    openEditor,
    closeEditor,
    parseSchema,
  }
}
