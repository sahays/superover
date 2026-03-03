import { useCallback } from 'react'
import { generateSceneCSV, generateSceneJSON, downloadFile } from '@/lib/scene-export'

interface UseSceneExportOptions {
  results: any[] | undefined
  sceneJob: any | undefined
  jobId: string | undefined
  filename?: string
}

export function useSceneExport({ results, sceneJob, jobId, filename }: UseSceneExportOptions) {
  const getDownloadFilename = useCallback((extension: string) => {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19).replace('T', '-')
    const baseFilename = filename ? filename.replace(/\.[^/.]+$/, '') : 'scene'
    const promptName = sceneJob?.prompt_name
      ? sceneJob.prompt_name.replace(/[^a-zA-Z0-9]/g, '_')
      : (sceneJob?.prompt_type || 'analysis')
    return `${baseFilename}_${promptName}_${timestamp}.${extension}`
  }, [filename, sceneJob])

  const isSubtitleJob = results && results.length > 0 &&
    (results[0].result_data?.prompt_type === 'subtitling' ||
     results[0].result_data?.prompt_type === 'transcription')

  const downloadAsJSON = useCallback(() => {
    if (!results || !sceneJob || !jobId) return
    const chunkDuration = sceneJob.config.chunk_duration || 0
    const jsonData = generateSceneJSON(results, chunkDuration, jobId, sceneJob.video_id, filename)
    downloadFile(jsonData, getDownloadFilename('json'), 'json')
  }, [results, sceneJob, jobId, filename, getDownloadFilename])

  const downloadAsCSV = useCallback(() => {
    if (!results || !sceneJob) return
    const chunkDuration = sceneJob.config.chunk_duration || 0
    const csvContent = generateSceneCSV(results, chunkDuration)
    downloadFile(csvContent, getDownloadFilename('csv'), 'csv')
  }, [results, sceneJob, getDownloadFilename])

  const downloadAsSRT = useCallback(() => {
    if (!results) return
    const srtContent = results
      .map((result: any) => result.result_data?.subtitle_text)
      .filter((text: string) => text)
      .join('\n\n')
    downloadFile(srtContent, getDownloadFilename('srt'), 'srt')
  }, [results, getDownloadFilename])

  return { isSubtitleJob, downloadAsJSON, downloadAsCSV, downloadAsSRT }
}
