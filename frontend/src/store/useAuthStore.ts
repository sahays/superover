import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthState {
  inviteCode: string | null
  isMaster: boolean
  // Admin grants master-level access everywhere except creating new invite
  // codes. Distinct from isMaster so the InviteCodesPage can hide the
  // Create button for admin-only users.
  isAdmin: boolean
  isAuthenticated: boolean
  login: (code: string, isMaster: boolean, isAdmin: boolean) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      inviteCode: null,
      isMaster: false,
      isAdmin: false,
      isAuthenticated: false,
      login: (code, isMaster, isAdmin) =>
        set({ inviteCode: code, isMaster, isAdmin, isAuthenticated: true }),
      logout: () =>
        set({ inviteCode: null, isMaster: false, isAdmin: false, isAuthenticated: false }),
    }),
    { name: 'superover-auth' }
  )
)
