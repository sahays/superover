import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { User, Notification, AppState } from '@/types';

interface AppStore extends AppState {
  // Actions
  setUser: (user: User | null) => void;
  setTheme: (theme: 'light' | 'dark') => void;
  toggleTheme: () => void;
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void;
  removeNotification: (id: string) => void;
  markNotificationAsRead: (id: string) => void;
  clearNotifications: () => void;
}

export const useAppStore = create<AppStore>()(
  persist(
    (set) => ({
      // Initial state
      user: null,
      theme: 'light',
      notifications: [],

      // Actions
      setUser: (user) =>
        set({ user }),

      setTheme: (theme) =>
        set({ theme }),

      toggleTheme: () =>
        set((state) => ({
          theme: state.theme === 'light' ? 'dark' : 'light',
        })),

      addNotification: (notification) =>
        set((state) => ({
          notifications: [
            {
              ...notification,
              id: Math.random().toString(36).substring(2, 9),
              timestamp: new Date().toISOString(),
              read: false,
            },
            ...state.notifications,
          ].slice(0, 50), // Keep only last 50 notifications
        })),

      removeNotification: (id) =>
        set((state) => ({
          notifications: state.notifications.filter((n) => n.id !== id),
        })),

      markNotificationAsRead: (id) =>
        set((state) => ({
          notifications: state.notifications.map((n) =>
            n.id === id ? { ...n, read: true } : n
          ),
        })),

      clearNotifications: () =>
        set({ notifications: [] }),
    }),
    {
      name: 'super-over-alchemy-app-store',
      partialize: (state) => ({
        user: state.user,
        theme: state.theme,
      }),
    }
  )
);