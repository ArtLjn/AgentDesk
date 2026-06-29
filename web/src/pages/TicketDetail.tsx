import { useCallback, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import { useTicket, useTicketTrace, useTraceDecisions } from '@/hooks/useApi'
import { useWebSocket } from '@/hooks/useWebSocket'
import type { Span, TraceDetail, TraceDecisionsResponse, WSMessage } from '@/types'
import { buildKnowledgeSearchParams } from '@/lib/knowledgeReference'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge, CategoryBadge, PriorityBadge } from '@/components/layout/StatusBadge'
import { TraceGantt } from '@/components/trace/TraceGantt'
import { SpanDetailSheet } from '@/components/trace/SpanDetailSheet'
import { DecisionTimeline } from '@/components/trace/DecisionTimeline'
import { LiveExecutionFlow } from '@/components/trace/LiveExecutionFlow'
import { Markdown } from '@/components/ui/markdown'
import { formatDuration } from '@/components/trace/spanTypes'
import {
  ArrowLeft, MessageSquare, Brain, Clock, Layers, Bot, Wrench,
  BookOpen, CheckCircle2, ExternalLink, Activity, Zap, GitFork,
} from 'lucide-react'

export function TicketDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: ticket, isLoading } = useTicket(id!)
  const ticketStatus = ticket?.status
  const isRunning = !!ticketStatus && !['completed', 'failed'].includes(ticketStatus)
  const { data: trace } = useTicketTrace(id!, isRunning)
  const traceDetail = trace as TraceDetail | undefined
  const traceId = traceDetail?.trace_id || ''
  const { data: decisionsResp } = useTraceDecisions(traceId)
  const decisions = (decisionsResp as TraceDecisionsResponse | undefined)?.decisions || []
  const flatSpans = useMemo(() => flattenSpans(traceDetail?.spans || []), [traceDetail])
  const [selectedSpan, setSelectedSpan] = useState<Span | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)

  const refreshTicketSnapshot = useCallback((msg: WSMessage) => {
    if (!id || msg.ticket_id !== id) return
    qc.invalidateQueries({ queryKey: ['ticket', id] })
    qc.invalidateQueries({ queryKey: ['tickets'] })
    qc.invalidateQueries({ queryKey: ['ticketTrace', id] })
    if (traceId) {
      qc.invalidateQueries({ queryKey: ['traceDecisions', traceId] })
    }
  }, [id, qc, traceId])

  useWebSocket(refreshTicketSnapshot)

  const slowestSpan = flatSpans.reduce<Span | null>((slowest, span) => {
    if (!slowest) return span
    return (span.duration || 0) > (slowest.duration || 0) ? span : slowest
  }, null)
  const llmCalls = flatSpans.filter((span) => span.span_type === 'llm_call').length
  const toolCalls = flatSpans.filter((span) => span.span_type === 'tool_call').length
  const reactIters = flatSpans.filter((span) => span.span_type === 'react_iter').length
  const errorCount = flatSpans.filter((span) => span.status === 'error').length

  const handleSelectSpan = (span: Span) => {
    setSelectedSpan(span)
    setSheetOpen(true)
  }

  if (isLoading || !ticket) {
    return <DetailSkeleton />
  }

  // 构建消息链
  const messages: { role: string; content: string }[] = []
  if (ticket.status) messages.push({ role: 'system', content: `工单创建，状态: ${ticket.status}` })
  if (ticket.category) messages.push({ role: 'classifier', content: `分类结果: ${ticket.category} | 优先级: ${ticket.priority || '-'}` })
  if (ticket.processing_result) messages.push({ role: 'processor', content: ticket.processing_result })
  if (ticket.references?.length) messages.push({ role: 'knowledge', content: `已引用 ${ticket.references.length} 条知识库片段` })
  if (ticket.review_score != null) messages.push({ role: 'reviewer', content: `审核评分: ${ticket.review_score.toFixed(2)} ${ticket.review_score >= 0.7 ? '(通过)' : '(未通过)'}` })
  if (ticket.error) messages.push({ role: 'coordinator', content: `错误: ${ticket.error}` })
  if (ticket.retry_count > 0) messages.push({ role: 'system', content: `已重试 ${ticket.retry_count} 次` })

  const buildKnowledgeHref = (reference: string) => `/knowledge?${buildKnowledgeSearchParams(reference).toString()}`

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="outline" size="sm" onClick={() => navigate('/tickets')}>
          <ArrowLeft className="w-4 h-4 mr-1" />
          返回
        </Button>
        <div>
          <h2 className="text-xl font-semibold font-mono">{ticket.ticket_id}</h2>
          <p className="text-sm text-muted-foreground">工单详情</p>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* 左侧：基本信息 + 消息链 */}
        <div className="col-span-5 space-y-4">
          {/* 基本信息卡片 */}
          <Card className="bg-card border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">工单信息</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <InfoField label="状态"><StatusBadge status={ticket.status} /></InfoField>
                <InfoField label="分类">{ticket.category ? <CategoryBadge category={ticket.category} /> : '-'}</InfoField>
                <InfoField label="优先级">{ticket.priority ? <PriorityBadge priority={ticket.priority} /> : '-'}</InfoField>
                <InfoField label="重试次数">
                  <span className="text-sm font-mono">{ticket.retry_count} / 3</span>
                </InfoField>
              </div>
              <Separator className="bg-border" />
              <InfoField label="工单内容">
                <div className="mt-1">
                  <Markdown>{ticket.content}</Markdown>
                </div>
              </InfoField>
              <Separator className="bg-border" />
              <InfoField label="处理结果">
                <div className="mt-1">
                  {ticket.processing_result
                    ? <Markdown>{ticket.processing_result}</Markdown>
                    : <span className="text-sm text-muted-foreground">等待处理...</span>}
                </div>
              </InfoField>
              {ticket.review_score != null && (
                <>
                  <Separator className="bg-border" />
                  <div className="grid grid-cols-2 gap-4">
                    <InfoField label="审核评分">
                      <span className={`text-lg font-bold ${ticket.review_score >= 0.7 ? 'text-success' : 'text-warning'}`}>
                        {ticket.review_score.toFixed(2)}
                      </span>
                    </InfoField>
                    <InfoField label="审核结果">
                      <Badge variant="outline" className={`border-0 ${ticket.review_score >= 0.7 ? 'bg-success/15 text-success' : 'bg-warning/15 text-warning'}`}>
                        {ticket.review_score >= 0.7 ? '通过' : '未通过'}
                      </Badge>
                    </InfoField>
                  </div>
                </>
              )}
              {ticket.references?.length > 0 && (
                <>
                  <Separator className="bg-border" />
                  <InfoField label="知识库参考">
                    <div className="mt-2 space-y-1.5">
                      {ticket.references.map((ref: string, index: number) => {
                        return (
                          <button
                            key={index}
                            type="button"
                            onClick={() => navigate(buildKnowledgeHref(ref))}
                            className="group block w-full text-left rounded-md border border-border bg-background px-2.5 py-1.5 transition-colors hover:border-primary/50 hover:bg-primary/5"
                            title="点击在知识库中检索相关文档"
                          >
                            <div className="flex items-start gap-2">
                              <BookOpen className="mt-0.5 h-3 w-3 shrink-0 text-primary" />
                              <p className="flex-1 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground group-hover:text-foreground">
                                {ref}
                              </p>
                              <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground/50 opacity-0 transition-opacity group-hover:opacity-100" />
                            </div>
                          </button>
                        )
                      })}
                    </div>
                  </InfoField>
                </>
              )}
            </CardContent>
          </Card>

          {/* Agent 消息链 */}
          <Card className="bg-card border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-primary" />
                Agent 消息链
                <span className="ml-auto text-[11px] font-normal text-muted-foreground">
                  共 {messages.length} 条
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[520px]">
                {messages.length === 0 ? (
                  <p className="text-muted-foreground text-sm text-center py-8">等待处理中...</p>
                ) : (
                  <div className="space-y-2 pr-2">
                    {messages.map((msg, i) => (
                      <div key={i} className="rounded-md bg-background border border-border p-2.5">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-[10px] font-mono uppercase tracking-wide text-primary bg-primary/10 rounded px-1.5 py-0.5">
                            {msg.role}
                          </span>
                          <span className="text-[10px] text-muted-foreground/60">#{i + 1}</span>
                        </div>
                        <Markdown>{msg.content}</Markdown>
                      </div>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </div>

        {/* 右侧：Trace 决策链 */}
        <div className="col-span-7 space-y-4">
          {/* 实时执行流（演示用：agent 工作过程动态展示） */}
          <LiveExecutionFlow
            ticketId={ticket.ticket_id}
            spans={traceDetail?.spans || []}
            isRunning={!['completed', 'failed'].includes(ticket.status)}
          />

          {traceDetail ? (
            <>
              {/* 决策链概览 */}
              <Card className="bg-card border-border">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Brain className="w-4 h-4 text-primary" />
                    决策链概览
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-5 gap-3">
                    <MiniStat icon={<Clock className="h-4 w-4" />} label="总耗时" value={traceDetail.duration != null ? formatDuration(traceDetail.duration) : '-'} />
                    <MiniStat icon={<Layers className="h-4 w-4" />} label="节点数" value={traceDetail.node_count} />
                    <MiniStat icon={<Bot className="h-4 w-4" />} label="LLM 调用" value={llmCalls} />
                    <MiniStat icon={<Wrench className="h-4 w-4" />} label="工具调用" value={toolCalls} />
                    <MiniStat icon={<Zap className="h-4 w-4" />} label="ReAct 推理" value={reactIters} />
                  </div>
                  {(slowestSpan || errorCount > 0) && (
                    <div className="mt-3 grid grid-cols-2 gap-3">
                      {slowestSpan && (
                        <div className="rounded-md border border-border bg-background p-3 text-xs">
                          <p className="text-muted-foreground mb-0.5">最耗时节点</p>
                          <p className="font-medium text-foreground truncate">{slowestSpan.name}</p>
                          <p className="font-mono text-primary mt-0.5">{formatDuration(slowestSpan.duration)}</p>
                        </div>
                      )}
                      <div className="rounded-md border border-border bg-background p-3 text-xs">
                        <p className="text-muted-foreground mb-0.5">错误节点</p>
                        <p className={`font-medium ${errorCount > 0 ? 'text-destructive' : 'text-success'}`}>
                          {errorCount > 0 ? `${errorCount} 个失败` : '全部成功'}
                        </p>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* 决策链甘特图（核心） */}
              <Card className="bg-card border-border">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Activity className="w-4 h-4 text-primary" />
                    决策链时间线
                    <span className="ml-auto text-[11px] font-normal text-muted-foreground">
                      点击节点查看完整输入/输出
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <TraceGantt
                    spans={traceDetail.spans || []}
                    onSelect={handleSelectSpan}
                  />
                </CardContent>
              </Card>

              {/* 决策点列表（v1.1 新增） */}
              <Card className="bg-card border-border">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <GitFork className="w-4 h-4 text-primary" />
                    决策点明细
                    <span className="ml-auto text-[11px] font-normal text-muted-foreground">
                      每个分岔路口 AI 的候选与选择
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <DecisionTimeline decisions={decisions} />
                </CardContent>
              </Card>

              {/* 处理结果摘要 */}
              {ticket.processing_result && (
                <Card className="bg-card border-border">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-success" />
                      处理结论
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Markdown>{ticket.processing_result}</Markdown>
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            <Card className="bg-card border-border">
              <CardContent className="py-16 text-center">
                <Brain className="h-10 w-10 mx-auto mb-3 text-muted-foreground/40" />
                <p className="text-sm text-muted-foreground">该工单暂无 Trace 数据</p>
                <p className="text-xs text-muted-foreground/70 mt-1">
                  工单被处理后将自动记录决策链
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      <SpanDetailSheet
        span={selectedSpan}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
      />
    </div>
  )
}

function InfoField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">{label}</p>
      {children}
    </div>
  )
}

function MiniStat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string | number }) {
  return (
    <div className="bg-background rounded-md p-2.5 border border-border">
      <div className="mb-1 text-primary">{icon}</div>
      <p className="text-base font-bold text-primary tabular-nums">{value}</p>
      <p className="text-[10px] text-muted-foreground">{label}</p>
    </div>
  )
}

function flattenSpans(spans: Span[]): Span[] {
  return spans.flatMap((span) => [span, ...flattenSpans(span.children || [])])
}

function DetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-60" />
      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-5 space-y-4">
          <Skeleton className="h-64 rounded-lg" />
          <Skeleton className="h-48 rounded-lg" />
        </div>
        <div className="col-span-7 space-y-4">
          <Skeleton className="h-32 rounded-lg" />
          <Skeleton className="h-96 rounded-lg" />
        </div>
      </div>
    </div>
  )
}
