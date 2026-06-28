/**
 * Trace 节点类型 → 颜色 / 中文标签 映射。
 * 参考设计：admin-web/src/constants/trace.ts。
 *
 * 用于甘特图、决策卡片、详情侧拉中的统一颜色编码。
 */

export type SpanType = 'node' | 'react_iter' | 'llm_call' | 'tool_call'
export type SpanStatus = 'ok' | 'error' | 'fallback'

export const SPAN_TYPE_COLORS: Record<SpanType, string> = {
  node: '#1890ff',        // 蓝 — 工作流节点
  react_iter: '#722ed1',  // 紫 — ReAct 推理
  llm_call: '#13c2c2',    // 青 — LLM 调用
  tool_call: '#52c41a',   // 绿 — 工具调用
}

export const SPAN_TYPE_LABELS: Record<SpanType, string> = {
  node: '工作流节点',
  react_iter: 'ReAct 推理',
  llm_call: 'LLM 调用',
  tool_call: '工具调用',
}

export const SPAN_TYPE_ICONS: Record<SpanType, string> = {
  node: 'route',
  react_iter: 'brain',
  llm_call: 'bot',
  tool_call: 'wrench',
}

export const SPAN_STATUS_COLORS: Record<SpanStatus, string> = {
  ok: '#52c41a',
  error: '#ff4d4f',
  fallback: '#faad14',
}

export const SPAN_STATUS_LABELS: Record<SpanStatus, string> = {
  ok: '成功',
  error: '失败',
  fallback: '降级',
}

export function getSpanTypeColor(type: string): string {
  return SPAN_TYPE_COLORS[type as SpanType] ?? '#8b949e'
}

export function getSpanTypeLabel(type: string): string {
  return SPAN_TYPE_LABELS[type as SpanType] ?? type
}

export function getSpanStatusColor(status: string): string {
  return SPAN_STATUS_COLORS[status as SpanStatus] ?? '#8b949e'
}

export function getSpanStatusLabel(status: string): string {
  return SPAN_STATUS_LABELS[status as SpanStatus] ?? status
}

/** 把秒转换为人类可读耗时 */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return '-'
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`
  if (seconds < 60) return `${seconds.toFixed(2)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m ${s}s`
}
