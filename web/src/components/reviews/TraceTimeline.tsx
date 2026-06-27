import { useMemo } from 'react'
import { Route, Clock, Layers } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useTicketTrace } from '@/hooks/useApi'
import type { Span, TraceDetail } from '@/types'
import { cn } from '@/lib/utils'

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

  const summary = useMemo(() => {
    if (!traceDetail) return null
    return {
      duration: traceDetail.duration,
      nodeCount: traceDetail.node_count,
      llmCalls: countSpans(traceDetail.spans, 'llm_call'),
      toolCalls: countSpans(traceDetail.spans, 'tool_call'),
    }
  }, [traceDetail])

  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between gap-2 text-sm">
          <span className="flex items-center gap-2">
            <Route className="h-4 w-4 text-primary" />
            执行 Trace 时间线
          </span>
          {summary && (
            <span className="flex items-center gap-3 text-[11px] text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {summary.duration != null ? `${summary.duration.toFixed(2)}s` : '-'}
              </span>
              <span className="inline-flex items-center gap-1">
                <Layers className="h-3 w-3" />
                {summary.nodeCount}
              </span>
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
          <ScrollArea className="max-h-[280px] pr-2">
            <div className="space-y-1.5">
              {traceDetail.spans.map((span) => (
                <TraceRow key={span.span_id} span={span} depth={0} />
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  )
}

function TraceRow({ span, depth }: { span: Span; depth: number }) {
  const isHuman = isHumanDecisionSpan(span)
  return (
    <div style={{ paddingLeft: depth * 14 }}>
      <div
        className={cn(
          'flex items-center gap-2 rounded-md border p-1.5 text-xs',
          isHuman
            ? 'border-[#a371f7]/40 bg-[#a371f7]/5'
            : 'border-border bg-background',
        )}
      >
        <div className={cn('h-1.5 w-1.5 rounded-full shrink-0', spanStatusDot[span.status] || 'bg-muted-foreground')} />
        <span className={cn('font-medium truncate', isHuman && 'text-[#a371f7]')}>{span.name}</span>
        {isHuman && (
          <Badge variant="outline" className="border-0 bg-[#a371f7]/15 px-1 py-0 text-[10px] text-[#a371f7]">
            当前节点
          </Badge>
        )}
        <span className="ml-auto font-mono text-[10px] text-muted-foreground shrink-0">
          {span.duration != null ? `${span.duration.toFixed(2)}s` : '-'}
        </span>
      </div>
      {span.children?.length > 0 && (
        <div className="mt-1 space-y-1">
          {span.children.map((c) => (
            <TraceRow key={c.span_id} span={c} depth={depth + 1} />
          ))}
        </div>
      )}
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
