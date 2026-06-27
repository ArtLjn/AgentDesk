import type { ReviewDecision } from '@/types'

export interface DecisionMeta {
  label: string
  color: string
  ring: string
}

export const decisionMeta: Record<ReviewDecision, DecisionMeta> = {
  approve: { label: '通过', color: 'bg-success text-success-foreground', ring: 'ring-success/30' },
  rewrite: { label: '改写', color: 'bg-primary text-primary-foreground', ring: 'ring-primary/30' },
  reprocess: { label: '重处理', color: 'bg-warning text-warning-foreground', ring: 'ring-warning/30' },
  reject: { label: '驳回', color: 'bg-destructive text-destructive-foreground', ring: 'ring-destructive/30' },
}

export const triggerLabels: Record<string, string> = {
  escalate: '升级',
  review_failed: '复核未通过',
  error_fallback: '错误兜底',
  user_request: '用户请求',
}

export const triggerStyles: Record<string, string> = {
  escalate: 'bg-[#a371f7]/15 text-[#a371f7]',
  review_failed: 'bg-warning/15 text-warning',
  error_fallback: 'bg-destructive/15 text-destructive',
  user_request: 'bg-primary/15 text-primary',
}

export function formatWaiting(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}秒`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}分钟`
  const hours = Math.floor(minutes / 60)
  return `${hours}小时${minutes % 60}分`
}

export function isWaitingTimeout(seconds: number): boolean {
  return seconds > 30 * 60
}
