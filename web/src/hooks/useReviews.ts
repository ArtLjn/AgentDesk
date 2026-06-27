import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { reviewsApi, type ReviewQueryParams } from '@/lib/reviews'
import type { ReviewDecisionRequest } from '@/types'

// 审核队列
export function useReviewQueue(params?: ReviewQueryParams) {
  return useQuery({
    queryKey: ['reviews', 'queue', params],
    queryFn: () => reviewsApi.getReviewQueue(params),
    refetchInterval: 15000,
  })
}

// 审核详情
export function useReviewDetail(ticketId: string | null) {
  return useQuery({
    queryKey: ['reviews', 'detail', ticketId],
    queryFn: () => reviewsApi.getReviewDetail(ticketId!),
    enabled: !!ticketId,
  })
}

// 审核统计
export function useReviewStats() {
  return useQuery({
    queryKey: ['reviews', 'stats'],
    queryFn: () => reviewsApi.getReviewStats(),
    refetchInterval: 30000,
  })
}

// 提交决策
export function useSubmitDecision() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ ticketId, body }: { ticketId: string; body: ReviewDecisionRequest }) =>
      reviewsApi.submitDecision(ticketId, body),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ['reviews', 'detail', vars.ticketId] })
      qc.invalidateQueries({ queryKey: ['reviews', 'queue'] })
      qc.invalidateQueries({ queryKey: ['reviews', 'stats'] })
      qc.invalidateQueries({ queryKey: ['tickets'] })
      qc.invalidateQueries({ queryKey: ['ticket', vars.ticketId] })
    },
  })
}
