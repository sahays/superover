import { useState, useCallback } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { videoApi, uploadToGCS } from '@/lib/api-client'
import type { ContextItem } from '@/lib/types'

interface ContextFile {
  file: File
  description: string
}

export function useContextUpload() {
  const [contextFiles, setContextFiles] = useState<ContextFile[]>([])
  const [uploadedContextItems, setUploadedContextItems] = useState<ContextItem[]>([])
  const [showContextUpload, setShowContextUpload] = useState(false)
  const [isUploadingContext, setIsUploadingContext] = useState(false)

  const handleFileUpload = useCallback(async (file: File) => {
    if (file.size > 10 * 1024 * 1024) {
      alert('File size must be less than 10MB')
      return
    }

    try {
      setIsUploadingContext(true)
      const { signed_url, gcs_path } = await videoApi.getContextSignedUrl(
        file.name,
        file.type || 'text/plain'
      )
      await uploadToGCS(signed_url, file)

      const contextItem: ContextItem = {
        context_id: uuidv4(),
        type: 'text',
        gcs_path,
        filename: file.name,
        description: '',
        size_bytes: file.size,
      }

      setUploadedContextItems(prev => [...prev, contextItem])
      setContextFiles(prev => [...prev, { file, description: '' }])
      setShowContextUpload(false)
    } catch (error) {
      console.error('Failed to upload context file:', error)
      alert('Failed to upload context file. Please try again.')
    } finally {
      setIsUploadingContext(false)
    }
  }, [])

  const removeContextFile = useCallback((index: number) => {
    setContextFiles(prev => prev.filter((_, i) => i !== index))
    setUploadedContextItems(prev => prev.filter((_, i) => i !== index))
  }, [])

  return {
    contextFiles,
    uploadedContextItems,
    showContextUpload,
    setShowContextUpload,
    isUploadingContext,
    handleFileUpload,
    removeContextFile,
  }
}
