/**
 * 单个决策点详情卡片：在 NodeDrawer / SpanDetailSheet 中展示。
 *
 * 与 DecisionTimeline（列表视图）不同，这个组件用于"单个 span 详情"
 * 场景，展示完整的 trigger / options / selection 信息。
 */

import { Route, GitBranch, ShieldCheck, AlertTriangle, Wrench, UserCheck } from 'lucide-react'
import type { DecisionOption } from '@/types'

const DECISION_STYLE: Record<
  string,
  { label: string; color: string; bg: string; icon: React.ReactNode }
> = {
  routing: { label: '路由', color: '#1890ff', bg: 'rgba(24,144,255,0.10)', icon: <Route className="h-3.5 w-3.5" /> },
  branching: { label: '分支', color: '#722ed1', bg: 'rgba(114,46,209,0.10)', icon: <GitBranch className="h-3.5 w-3.5" /> },
  quality_gate: { label: '质量门', color: '#13c2c2', bg: 'rgba(19,194,194,0.10)', icon: <ShieldCheck className="h-3.5 w-3.5" /> },
  boundary: { label: '边界', color: '#faad14', bg: 'rgba(250,173,20,0.12)', icon: <AlertTriangle className="h-3.5 w-3.5" /> },
  tool_selection: { label: '工具', color: '#8b949e', bg: 'rgba(139,148,158,0.12)', icon: <Wrench className="h-3.5 w-3.5" /> },
  escalation: { label: '人工', color: '#ff4d4f', bg: 'rgba(255,77,79,0.10)', icon: <UserCheck className="h-3.5 w-3.5" /> },
}

function getStyle(type: string) {
  return DECISION_STYLE[type] ?? {
    label: type,
    color: '#8b949e',
    bg: 'rgba(139,148,158,0.12)',
    icon: <AlertTriangle className="h-3.5 w-3.5" />,
  }
}

function confidenceColor(c: number | null | undefined): string {
  if (c == null) return '#8b949e'
  if (c < 0.5) return '#ff4d4f'
  if (c < 0.7) return '#faad14'
  if (c < 0.9) return '#fadb14'
  return '#52c41a'
}

export interface DecisionData {
  decision_type: string
  trigger?: Record<string, unknown> | null
  options?: DecisionOption[]
  selection?: {
    value?: string
    confidence?: number | null
    reason?: string | null
  } | null
  execution?: Record<string, unknown> | null
}

interface DecisionCardProps {
  decision: DecisionData
}

export function DecisionCard({ decision }: DecisionCardProps) {
  const style = getStyle(decision.decision_type)
  const selection = decision.selection || {}
  const options = decision.options || []
  const conf = selection.confidence

  return (
    <div className="rounded-md border border-border bg-card p-3">
      <div className="flex items-center gap-2 mb-2.5">
        <span
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium"
          style={{ backgroundColor: style.bg, color: style.color }}
        >
          {style.icon}
          {style.label}
        </span>
        {conf != null && (
          <span
            className="ml-auto font-mono text-[11px]"
            style={{ color: confidenceColor(conf) }}
          >
            置信度 {(conf * 100).toFixed(0)}%
          </span>
        )}
      </div>

      <div className="grid grid-cols-[80px_1fr] gap-x-3 gap-y-1.5 text-xs">
        <span className="text-muted-foreground">最终选择</span>
        <span className="font-semibold text-foreground">{selection.value || '-'}</span>

        {selection.reason && (
          <>
            <span className="text-muted-foreground">选择理由</span>
            <span className="text-foreground/85 leading-relaxed">{selection.reason}</span>
          </>
        )}

        {decision.trigger && Object.keys(decision.trigger).length > 0 && (
          <>
            <span className="text-muted-foreground">触发信号</span>
            <span className="font-mono text-[11px] text-muted-foreground break-all">
              {JSON.stringify(decision.trigger)}
            </span>
          </>
        )}
      </div>

      {options.length > 0 && (
        <div className="mt-2.5">
          <p className="text-[11px] text-muted-foreground mb-1">候选方案（{options.length}）</p>
          <div className="space-y-1">
            {options.map((opt, i) => {
              const isSel = opt.value === selection.value
              const pct = Math.max(2, Math.round((opt.score || 0) * 100))
              return (
                <div key={opt.value + i} className="flex items-center gap-2">
                  <span className={`w-24 truncate ${isSel ? 'font-medium text-foreground' : 'text-muted-foreground'}`}>
                    {opt.value}
                  </span>
                  <div className="flex-1 h-1.5 rounded bg-muted overflow-hidden">
                    <div
                      className="h-full rounded"
                      style={{
                        width: `${pct}%`,
                        backgroundColor: isSel ? style.color : '#8b949e',
                        opacity: isSel ? 1 : 0.5,
                      }}
                    />
                  </div>
                  <span className="w-10 text-right font-mono text-[11px] text-muted-foreground">
                    {(opt.score || 0).toFixed(2)}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
