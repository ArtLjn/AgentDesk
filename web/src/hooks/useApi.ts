import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

// 工单
export function useTickets(params?: Record<string, string>) {
  return useQuery({
    queryKey: ['tickets', params],
    queryFn: () => api.getTickets(params),
    refetchInterval: 10000,
  })
}

export function useTicket(id: string) {
  return useQuery({
    queryKey: ['ticket', id],
    queryFn: () => api.getTicket(id),
    enabled: !!id,
  })
}

export function useCreateTicket() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { content: string; user_id?: string }) => api.createTicket(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tickets'] }),
  })
}

// Trace
export function useTraces(params?: Record<string, string>) {
  return useQuery({
    queryKey: ['traces', params],
    queryFn: () => api.getTraces(params),
    refetchInterval: 15000,
  })
}

export function useTicketTrace(ticketId: string) {
  return useQuery({
    queryKey: ['ticketTrace', ticketId],
    queryFn: () => api.getTicketTrace(ticketId),
    enabled: !!ticketId,
  })
}

export function useTraceStats(traceId: string) {
  return useQuery({
    queryKey: ['traceStats', traceId],
    queryFn: () => api.getTraceStats(traceId),
    enabled: !!traceId,
  })
}

// Analytics
export function useAnalytics() {
  return useQuery({
    queryKey: ['analytics'],
    queryFn: () => api.getAnalytics(),
    refetchInterval: 30000,
  })
}

// Knowledge
export function useKnowledge(params?: Record<string, string>) {
  return useQuery({
    queryKey: ['knowledge', params],
    queryFn: () => api.getKnowledge(params),
  })
}

export function useUploadKnowledge() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { title: string; content: string; category?: string }) =>
      api.uploadKnowledge(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledge'] }),
  })
}

// Settings
export function useSystemSettings() {
  return useQuery({
    queryKey: ['systemSettings'],
    queryFn: () => api.getSettings(),
  })
}
