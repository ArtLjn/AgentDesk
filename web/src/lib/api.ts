const BASE_URL = '/api'

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) {
    throw new Error(`API Error: ${res.status} ${res.statusText}`)
  }
  return res.json()
}

// Tickets
export const api = {
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
    return request<{ traces: any[]; count: number }>(`/traces${qs}`)
  },
  getTicketTrace: (ticketId: string) => request<any>(`/tickets/${ticketId}/trace`),
  getTraceStats: (traceId: string) => request<any>(`/traces/${traceId}/stats`),

  // Analytics
  getAnalytics: () => request<any>('/analytics'),

  // Knowledge
  uploadKnowledge: (data: { title: string; content: string; category?: string }) =>
    request<any>('/knowledge', { method: 'POST', body: JSON.stringify(data) }),

  // Health
  getHealth: () => request<any>('/health'),
}
