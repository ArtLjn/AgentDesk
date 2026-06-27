import { create } from 'zustand'

export type ToastKind = 'info' | 'success' | 'warning' | 'error'

export interface ToastItem {
  id: string
  kind: ToastKind
  title: string
  description?: string
}

interface ToastState {
  toasts: ToastItem[]
  push: (kind: ToastKind, title: string, description?: string, ttlMs?: number) => string
  dismiss: (id: string) => void
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (kind, title, description, ttlMs = 4000) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    set((s) => ({ toasts: [...s.toasts, { id, kind, title, description }] }))
    if (ttlMs > 0) {
      setTimeout(() => {
        set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }))
      }, ttlMs)
    }
    return id
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))

export const toast = {
  info: (title: string, description?: string) => useToastStore.getState().push('info', title, description),
  success: (title: string, description?: string) => useToastStore.getState().push('success', title, description),
  warning: (title: string, description?: string) => useToastStore.getState().push('warning', title, description),
  error: (title: string, description?: string) => useToastStore.getState().push('error', title, description),
}
