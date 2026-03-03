import { Routes, Route } from 'react-router-dom'
import { AppLayout } from '@/components/layout/app-layout'
import HomePage from '@/pages/HomePage'
import MediaPage from '@/pages/MediaPage'
import MediaJobDetailPage from '@/pages/MediaJobDetailPage'
import SceneAnalysisPage from '@/pages/SceneAnalysisPage'
import SceneDetailPage from '@/pages/SceneDetailPage'
import PromptsPage from '@/pages/PromptsPage'
import EditPromptPage from '@/pages/EditPromptPage'
import SearchPage from '@/pages/SearchPage'
import SearchSyncPage from '@/pages/SearchSyncPage'

export function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/media" element={<MediaPage />} />
        <Route path="/media/:jobId" element={<MediaJobDetailPage />} />
        <Route path="/scene-analysis" element={<SceneAnalysisPage />} />
        <Route path="/scene/:id" element={<SceneDetailPage />} />
        <Route path="/prompts" element={<PromptsPage />} />
        <Route path="/prompts/:promptId" element={<EditPromptPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/search/sync" element={<SearchSyncPage />} />
      </Routes>
    </AppLayout>
  )
}
