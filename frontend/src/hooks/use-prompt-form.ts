import { useState, useCallback } from 'react'
import type { Prompt } from '@/lib/types'

export interface PromptFormData {
  name: string
  type: string
  prompt_text: string
  supports_context?: boolean
  context_description?: string
}

const INITIAL_FORM: PromptFormData = {
  name: '',
  type: 'scene_analysis',
  prompt_text: '',
  supports_context: false,
  context_description: '',
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
      supports_context: prompt.supports_context || false,
      context_description: prompt.context_description || '',
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

    setFormErrors(errors)
    return Object.keys(errors).length === 0
  }, [formData])

  return { formData, setFormData, formErrors, resetForm, populateFrom, validateForm }
}
