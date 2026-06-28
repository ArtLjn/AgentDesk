/**
 * 决策时间线：垂直展示一次 trace 内的所有决策点。
 * 每项含决策类型徽章、候选数、置信度条、最终选择值与理由。
 *
 * 数据来源：GET /api/traces/{trace_id}/decisions
 * 决策数据来自后端 span.metadata.decision 子结构。
 */

import { GitBranch, ShieldCheck, AlertTriangle, Wrench, UserCheck, Route } from 'lucide-react'
import type { TraceDecision } from '@/types'
import { formatDuration } from './spanTypes'

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

function confidenceColor(c: number | null): string {
  if (c == null) return '#8b949e'
  if (c < 0.5) return '#ff4d4f'
  if (c < 0.7) return '#faad14'
  if (c < 0.9) return '#fadb14'
  return '#52c41a'
}

interface DecisionTimelineProps {
  decisions: TraceDecision[]
}

export function DecisionTimeline({ decisions }: DecisionTimelineProps) {
  if (!decisions || decisions.length === 0) {
    return (
      <div className="text-center py-8 text-sm text-muted-foreground">
        该 trace 暂无决策点数据
      </div>
    )
  }

  return (
    <ol className="relative space-y-3 before:absolute before:left-[15px] before:top-2 before:bottom-2 before:w-px before:bg-border">
      {decisions.map((d, idx) => {
        const style = getStyle(d.decision_type)
        const conf = d.confidence
        const topOption = [...d.options].sort((a, b) => b.score - a.score)[0]
        return (
          <li key={d.span_id + idx} className="relative pl-10">
            <span
              className="absolute left-0 top-1 flex h-8 w-8 items-center justify-center rounded-full border"
              style={{ backgroundColor: style.bg, borderColor: style.color, color: style.color }}
            >
              {style.icon}
            </span>

            <div className="rounded-md border border-border bg-card p-3 text-xs">
              <div className="flex items-center gap-2 mb-1.5">
                <span
                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium"
                  style={{ backgroundColor: style.bg, color: style.color }}
                >
                  {style.label}
                </span>
                <span className="font-mono text-muted-foreground">{d.span_name}</span>
                {d.duration != null && (
                  <span className="ml-auto font-mono text-muted-foreground">
                    {formatDuration(d.duration)}
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-muted-foreground">最终选择</span>
                <span className="font-semibold text-foreground">{d.selection_value || '-'}</span>
                {conf != null && (
                  <span
                    className="ml-auto font-mono text-[11px]"
                    style={{ color: confidenceColor(conf) }}
                  >
                    置信度 {(conf * 100).toFixed(0)}%
                  </span>
                )}
              </div>

              {d.reason && (
                <p className="text-muted-foreground mb-1.5 leading-relaxed">{d.reason}</p>
              )}

              {d.options && d.options.length > 0 && (
                <div className="space-y-1">
                  <p className="text-[11px] text-muted-foreground">
                    候选 ({d.options_count})
                  </p>
                  {d.options.map((opt, i) => {
                    const isSel = opt.value === d.selection_value
                    const pct = Math.max(2, Math.round((opt.score || 0) * 100))
                    return (
                      <div key={opt.value + i} className="flex items-center gap-2">
                        <span className={`w-20 truncate ${isSel ? 'font-medium text-foreground' : 'text-muted-foreground'}`}>
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
              )}

              {topOption && d.options.length === 0 && (
                <p className="text-[11px] text-muted-foreground">无候选明细</p>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
