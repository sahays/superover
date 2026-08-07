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
import EngagementAnalysisPage from '@/pages/EngagementAnalysisPage'
import EngagementNewPage from '@/pages/EngagementNewPage'
import EngagementResultsPage from '@/pages/EngagementResultsPage'
import PromptsPage from '@/pages/PromptsPage'
import CreatePromptPage from '@/pages/CreatePromptPage'
import EditPromptPage from '@/pages/EditPromptPage'
import SearchPage from '@/pages/SearchPage'
import SearchSyncPage from '@/pages/SearchSyncPage'
import BrandingPage from '@/pages/BrandingPage'
import InviteCodesPage from '@/pages/InviteCodesPage'
import AvatarsPage from '@/pages/AvatarsPage'
import AvatarCreatePage from '@/pages/AvatarCreatePage'
import AvatarPage from '@/pages/AvatarPage'
import DubbingPage from '@/pages/DubbingPage'
import DubbingNewPage from '@/pages/DubbingNewPage'
import DubbingDetailPage from '@/pages/DubbingDetailPage'

export function App() {
  const { isAuthenticated, isMaster, isAdmin, inviteCode, logout } = useAuthStore()
  // Master and admin see the same set of routes — admin = master for
  // navigation. The only master-only privilege is creating new invite
  // codes, enforced inside InviteCodesPage and the API.
  const elevated = isMaster || isAdmin

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
        <Route path="/dubbing" element={<DubbingPage />} />
        <Route path="/dubbing/new" element={<DubbingNewPage />} />
        <Route path="/dubbing/:jobId" element={<DubbingDetailPage />} />
        <Route path="/engagement" element={<EngagementAnalysisPage />} />

        {elevated && <Route path="/engagement/new" element={<EngagementNewPage />} />}
        <Route path="/engagement/:jobId" element={<EngagementResultsPage />} />
        <Route path="/prompts" element={<PromptsPage />} />
        {elevated && <Route path="/prompts/new" element={<CreatePromptPage />} />}
        <Route path="/prompts/:promptId" element={<EditPromptPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/search/avatar" element={<SearchPage />} />
        {elevated && (
          <>
            <Route path="/avatars" element={<AvatarsPage />} />
            <Route path="/avatars/create" element={<AvatarCreatePage />} />
            <Route path="/avatars/:id" element={<AvatarPage />} />
            <Route path="/search/sync" element={<SearchSyncPage />} />
            <Route path="/branding" element={<BrandingPage />} />
          </>
        )}
        {isMaster && <Route path="/invite-codes" element={<InviteCodesPage />} />}
      </Routes>
    </AppLayout>
  )
}
