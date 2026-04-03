import { useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import { AppLayout } from '@/components/layout/app-layout'
import { InviteCodeGate } from '@/components/auth/InviteCodeGate'
import { useAuthStore } from '@/store/useAuthStore'
import { authApi } from '@/lib/api-client'
import HomePage from '@/pages/HomePage'
import MediaPage from '@/pages/MediaPage'
import MediaJobDetailPage from '@/pages/MediaJobDetailPage'
import SceneAnalysisPage from '@/pages/SceneAnalysisPage'
import SceneDetailPage from '@/pages/SceneDetailPage'
import SceneResultsPage from '@/pages/SceneResultsPage'
import PromptsPage from '@/pages/PromptsPage'
import CreatePromptPage from '@/pages/CreatePromptPage'
import EditPromptPage from '@/pages/EditPromptPage'
import SearchPage from '@/pages/SearchPage'
import SearchSyncPage from '@/pages/SearchSyncPage'
import BrandingPage from '@/pages/BrandingPage'
import InviteCodesPage from '@/pages/InviteCodesPage'

export function App() {
  const { isAuthenticated, isMaster, inviteCode, logout } = useAuthStore()

  // Re-validate stored code on mount
  useEffect(() => {
    if (!isAuthenticated || !inviteCode) return
    authApi.validate(inviteCode).then((result) => {
      if (!result.valid) logout()
    }).catch(() => {})
  }, [isAuthenticated, inviteCode, logout])

  if (!isAuthenticated) {
    return <InviteCodeGate />
  }

  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/media" element={<MediaPage />} />
        <Route path="/media/:jobId" element={<MediaJobDetailPage />} />
        <Route path="/scene-analysis" element={<SceneAnalysisPage />} />
        <Route path="/scene/:id" element={<SceneDetailPage />} />
        <Route path="/scene/:id/results" element={<SceneResultsPage />} />
        <Route path="/prompts" element={<PromptsPage />} />
        {isMaster && <Route path="/prompts/new" element={<CreatePromptPage />} />}
        <Route path="/prompts/:promptId" element={<EditPromptPage />} />
        <Route path="/search" element={<SearchPage />} />
        {isMaster && (
          <>
            <Route path="/search/sync" element={<SearchSyncPage />} />
            <Route path="/branding" element={<BrandingPage />} />
            <Route path="/invite-codes" element={<InviteCodesPage />} />
          </>
        )}
      </Routes>
    </AppLayout>
  )
}
