import { useMemo, useState } from 'react'
import { ChevronDown, ChevronRight, Clock, Layers, Route } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useTicketTrace } from '@/hooks/useApi'
import type { Span, TraceDetail } from '@/types'
import { cn } from '@/lib/utils'
import { FieldList, extractFields } from '@/components/trace/spanFormat'
import { formatDuration, getSpanTypeLabel } from '@/components/trace/spanTypes'

interface Props {
  ticketId: string
}

const spanStatusDot: Record<string, string> = {
  ok: 'bg-success',
  error: 'bg-destructive',
  fallback: 'bg-warning',
}

function isHumanDecisionSpan(span: Span): boolean {
  return (
    span.name === 'human_decision' ||
    span.name.includes('review') && span.name.includes('human')
  )
}

export function TraceTimeline({ ticketId }: Props) {
  const { data: trace, isLoading } = useTicketTrace(ticketId)
  const traceDetail = trace as TraceDetail | undefined
  const [manualExpandedIds, setManualExpandedIds] = useState<Set<string> | null>(null)
  const detailSpanIds = useMemo(
    () => collectDetailSpanIds(traceDetail?.spans || []),
    [traceDetail],
  )
  const defaultExpandedIds = useMemo(
    () => new Set(detailSpanIds.filter((span) => isHumanDecisionSpan(span)).map((span) => span.span_id)),
    [detailSpanIds],
  )
  const expandedIds = manualExpandedIds ?? defaultExpandedIds

  const summary = useMemo(() => {
    if (!traceDetail) return null
    return {
      duration: traceDetail.duration,
      nodeCount: traceDetail.node_count,
      llmCalls: countSpans(traceDetail.spans, 'llm_call'),
      toolCalls: countSpans(traceDetail.spans, 'tool_call'),
    }
  }, [traceDetail])

  const toggleSpan = (spanId: string) => {
    setManualExpandedIds((current) => {
      const base = current ?? expandedIds
      const next = new Set(base)
      if (next.has(spanId)) {
        next.delete(spanId)
      } else {
        next.add(spanId)
      }
      return next
    })
  }

  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between gap-2 text-sm">
          <span className="flex items-center gap-2">
            <Route className="h-4 w-4 text-primary" />
            执行 Trace 时间线
          </span>
          {summary && (
            <span className="flex items-center gap-2 text-[11px] text-muted-foreground">
              <span className="flex items-center gap-3">
                <span className="inline-flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {summary.duration != null ? formatDuration(summary.duration) : '-'}
                </span>
                <span className="inline-flex items-center gap-1">
                  <Layers className="h-3 w-3" />
                  {summary.nodeCount}
                </span>
              </span>
              {detailSpanIds.length > 0 && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-[11px]"
                  onClick={() => {
                    if (expandedIds.size >= detailSpanIds.length) {
                      setManualExpandedIds(new Set())
                    } else {
                      setManualExpandedIds(new Set(detailSpanIds.map((span) => span.span_id)))
                    }
                  }}
                >
                  {expandedIds.size >= detailSpanIds.length ? '收起全部' : '展开全部'}
                </Button>
              )}
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-32 rounded-md" />
        ) : !traceDetail || !traceDetail.spans?.length ? (
          <p className="text-center text-xs text-muted-foreground py-6">暂无 trace 数据</p>
        ) : (
          <div className="max-h-[560px] space-y-1.5 overflow-y-auto pr-2">
            {traceDetail.spans.map((span) => (
              <TraceRow
                key={span.span_id}
                span={span}
                depth={0}
                expandedIds={expandedIds}
                onToggle={toggleSpan}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function TraceRow({
  span,
  depth,
  expandedIds,
  onToggle,
}: {
  span: Span
  depth: number
  expandedIds: Set<string>
  onToggle: (spanId: string) => void
}) {
  const isHuman = isHumanDecisionSpan(span)
  const inputFields = extractFields(span.input_data)
  const outputFields = extractFields(span.output_data)
  const metaFields = extractFields(span.metadata)
  const hasDetail = inputFields.length > 0 || outputFields.length > 0 || metaFields.length > 0
  const expanded = expandedIds.has(span.span_id)

  return (
    <div className="min-w-0" style={{ paddingLeft: depth * 14 }}>
      <button
        type="button"
        disabled={!hasDetail}
        onClick={() => hasDetail && onToggle(span.span_id)}
        className={cn(
          'flex min-w-0 w-full items-center gap-2 rounded-md border p-1.5 text-left text-xs transition-colors',
          hasDetail && 'hover:border-primary/50 hover:bg-primary/5',
          isHuman
            ? 'border-[#a371f7]/40 bg-[#a371f7]/5'
            : 'border-border bg-background',
        )}
      >
        {hasDetail ? (
          <span className="shrink-0 text-muted-foreground">
            {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </span>
        ) : (
          <span className="w-3.5 shrink-0" />
        )}
        <div className={cn('h-1.5 w-1.5 rounded-full shrink-0', spanStatusDot[span.status] || 'bg-muted-foreground')} />
        <span className={cn('font-medium truncate', isHuman && 'text-[#a371f7]')}>{span.name}</span>
        <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
          {getSpanTypeLabel(span.span_type)}
        </span>
        {isHuman && (
          <Badge variant="outline" className="border-0 bg-[#a371f7]/15 px-1 py-0 text-[10px] text-[#a371f7]">
            当前节点
          </Badge>
        )}
        <span className="ml-auto font-mono text-[10px] text-muted-foreground shrink-0">
          {formatDuration(span.duration)}
        </span>
      </button>
      {expanded && hasDetail && (
        <div className="mt-1 rounded-md border border-border bg-background/70 p-2">
          <TraceDetailFields title="输入" fields={inputFields} />
          <TraceDetailFields title="输出" fields={outputFields} />
          <TraceDetailFields title="元数据" fields={metaFields} />
        </div>
      )}
      {span.children?.length > 0 && (
        <div className="mt-1 space-y-1">
          {span.children.map((c) => (
            <TraceRow
              key={c.span_id}
              span={c}
              depth={depth + 1}
              expandedIds={expandedIds}
              onToggle={onToggle}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function TraceDetailFields({ title, fields }: { title: string; fields: ReturnType<typeof extractFields> }) {
  if (fields.length === 0) return null
  return (
    <div className="mb-2 last:mb-0">
      <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">{title}</p>
      <FieldList fields={fields} />
    </div>
  )
}

function countSpans(spans: Span[], type: Span['span_type']): number {
  let count = 0
  for (const s of spans) {
    if (s.span_type === type) count++
    if (s.children?.length) count += countSpans(s.children, type)
  }
  return count
}

function collectDetailSpanIds(spans: Span[]): Span[] {
  const result: Span[] = []
  for (const span of spans) {
    const hasDetail =
      extractFields(span.input_data).length > 0 ||
      extractFields(span.output_data).length > 0 ||
      extractFields(span.metadata).length > 0
    if (hasDetail) result.push(span)
    if (span.children?.length) result.push(...collectDetailSpanIds(span.children))
  }
  return result
}
