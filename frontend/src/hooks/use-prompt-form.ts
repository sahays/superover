import { useState, useCallback } from 'react'
import type { Prompt } from '@/lib/types'

export interface PromptFormData {
  name: string
  type: string
  prompt_text: string
  schema_name?: string
  supports_context?: boolean
  context_description?: string
  response_type?: string
  response_schema_json?: string
}

const INITIAL_FORM: PromptFormData = {
  name: '',
  type: 'scene_analysis',
  prompt_text: '',
  schema_name: undefined,
  supports_context: false,
  context_description: '',
  response_type: 'structured_json',
  response_schema_json: '',
}

export function usePromptForm() {
  const [formData, setFormData] = useState<PromptFormData>(INITIAL_FORM)
  const [formErrors, setFormErrors] = useState<Partial<PromptFormData>>({})

  const resetForm = useCallback(() => {
    setFormData(INITIAL_FORM)
    setFormErrors({})
  }, [])

  const populateFrom = useCallback((prompt: Prompt) => {
    setFormData({
      name: prompt.name,
      type: prompt.type,
      prompt_text: prompt.prompt_text,
      schema_name: prompt.schema_name || undefined,
      supports_context: prompt.supports_context || false,
      context_description: prompt.context_description || '',
      response_type: prompt.response_type || undefined,
      response_schema_json: prompt.response_schema ? JSON.stringify(prompt.response_schema, null, 2) : '',
    })
    setFormErrors({})
  }, [])

  const validateForm = useCallback((): boolean => {
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

    if (formData.response_type === 'structured_json') {
      if (!formData.response_schema_json?.trim()) {
        errors.response_schema_json = 'JSON schema is required for structured output'
      } else {
        try {
          JSON.parse(formData.response_schema_json)
        } catch {
          errors.response_schema_json = 'Invalid JSON'
        }
      }
    }

    setFormErrors(errors)
    return Object.keys(errors).length === 0
  }, [formData])

  return { formData, setFormData, formErrors, resetForm, populateFrom, validateForm }
}
