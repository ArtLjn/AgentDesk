import type { KnowledgeListResponse, TraceListResponse } from '@/types'

const BASE_URL = '/api'

export class ApiError extends Error {
  status: number
  detail?: string

  constructor(status: number, statusText: string, detail?: string) {
    super(detail || `API Error: ${status} ${statusText}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

/** 401 时跳转登录页（避免循环跳转：当前已经在登录页则不跳）。 */
function handleUnauthorized() {
  if (window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
}

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (res.status === 401) {
    handleUnauthorized()
  }
  if (!res.ok) {
    let detail: string | undefined
    try {
      const body = await res.json()
      detail = typeof body?.detail === 'string' ? body.detail : undefined
    } catch {
      detail = undefined
    }
    throw new ApiError(res.status, res.statusText, detail)
  }
  return res.json()
}

export interface AuthState {
  logged_in: boolean
  username: string | null
  auth_enabled: boolean
}

export const api = {
  // 鉴权
  login: (username: string, password: string) =>
    request<{ username: string; logged_in: boolean }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request<{ logged_out: boolean }>('/auth/logout', { method: 'POST' }),
  getAuthState: () => request<AuthState>('/auth/me'),

  // 工单
  getTickets: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return request<any[]>(`/tickets${qs}`)
  },
  getTicket: (id: string) => request<any>(`/tickets/${id}`),
  createTicket: (data: { content: string; user_id?: string }) =>
    request<any>('/tickets', { method: 'POST', body: JSON.stringify(data) }),
  submitFeedback: (id: string, satisfied: boolean) =>
    request<any>(`/tickets/${id}/feedback`, { method: 'POST', body: JSON.stringify({ satisfied }) }),

  // Trace
  getTraces: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return request<TraceListResponse>(`/traces${qs}`)
  },
  getTicketTrace: (ticketId: string) => request<any>(`/tickets/${ticketId}/trace`),
  getTraceStats: (traceId: string) => request<any>(`/traces/${traceId}/stats`),

  // Analytics
  getAnalytics: () => request<any>('/analytics'),

  // Knowledge
  getKnowledge: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return request<KnowledgeListResponse>(`/knowledge${qs}`)
  },
  uploadKnowledge: (data: { title: string; content: string; category?: string }) =>
    request<any>('/knowledge', { method: 'POST', body: JSON.stringify(data) }),

  // Settings
  getSettings: () => request<any>('/settings'),

  // Health（不鉴权，供前端探活）
  getHealth: () => request<any>('/health'),
}
