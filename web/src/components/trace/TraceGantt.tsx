/**
 * 工单 Trace 的水平甘特图。
 * 参考 admin-web GanttTimeline，但适配当前项目的扁平 span 结构。
 *
 * 每行展示一个 span：类型圆点 · 名称 · 开始时间 · 耗时 · 状态 · 时间线条。
 */
import type { Span } from '@/types'
import {
  formatDuration,
  getSpanStatusColor,
  getSpanTypeColor,
  getSpanTypeLabel,
} from './spanTypes'

interface FlatSpan extends Span {
  depth: number
}

export interface TraceGanttProps {
  spans: Span[]
  onSelect?: (span: Span) => void
}

export function TraceGantt({ spans, onSelect }: TraceGanttProps) {
  const flat = flattenSpans(spans)
  const maxDuration = Math.max(...flat.map((s) => s.duration || 0), 0.001)

  if (flat.length === 0) {
    return (
      <div className="rounded-md border border-border bg-muted/20 py-8 text-center text-xs text-muted-foreground">
        暂无执行链路数据
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-md border border-border">
      {/* 表头 */}
      <div className="flex items-center gap-3 border-b border-border bg-muted/30 px-3 py-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        <div className="w-[200px]">节点</div>
        <div className="w-[80px] text-right">耗时</div>
        <div className="w-[70px] text-center">状态</div>
        <div className="flex-1">耗时分布</div>
      </div>

      {/* 节点行 */}
      <div className="divide-y divide-border">
        {flat.map((span) => {
          const color = getSpanTypeColor(span.span_type)
          const widthPct = Math.max(((span.duration || 0) / maxDuration) * 100, 2)
          const isError = span.status === 'error'
          return (
            <button
              key={span.span_id}
              type="button"
              onClick={() => onSelect?.(span)}
              className="flex w-full items-center gap-3 px-3 py-2 text-left transition-colors hover:bg-muted/40"
              style={{ paddingLeft: 12 + span.depth * 16 }}
            >
              {/* 节点名称 */}
              <div className="flex w-[200px] items-center gap-2 overflow-hidden">
                <span
                  className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ background: isError ? getSpanStatusColor(span.status) : color }}
                  title={getSpanTypeLabel(span.span_type)}
                />
                <span className="truncate text-[13px] text-foreground" title={span.name}>
                  {span.name}
                </span>
              </div>

              {/* 耗时 */}
              <div className="w-[80px] text-right font-mono text-[12px] tabular-nums text-muted-foreground">
                {formatDuration(span.duration)}
              </div>

              {/* 状态 */}
              <div className="w-[70px] text-center">
                <span
                  className="inline-block rounded-full px-2 py-0.5 text-[10px] font-medium"
                  style={{
                    color: getSpanStatusColor(span.status),
                    background: `${getSpanStatusColor(span.status)}20`,
                  }}
                >
                  {span.status}
                </span>
              </div>

              {/* 时间线条形图 */}
              <div className="relative h-5 flex-1 overflow-hidden rounded bg-muted/40">
                <div
                  className="absolute inset-y-0 left-0 rounded"
                  style={{ width: `${widthPct}%`, background: color, opacity: 0.85 }}
                  title={`${span.name}: ${formatDuration(span.duration)}`}
                />
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function flattenSpans(spans: Span[], depth = 0): FlatSpan[] {
  return spans.flatMap((span) => [
    { ...span, depth },
    ...flattenSpans(span.children || [], depth + 1),
  ])
}
