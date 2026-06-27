import { useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useTicket, useTicketTrace } from '@/hooks/useApi'
import type { Span, TraceDetail } from '@/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge, CategoryBadge, PriorityBadge } from '@/components/layout/StatusBadge'
import {
  ArrowLeft, Bot, Cpu, Wrench, Eye, MessageSquare, Brain, Route,
  ChevronRight, ChevronDown, FileJson, ArrowRightLeft, Info,
  BookOpen, CheckCircle2, Clock, Layers, ExternalLink,
} from 'lucide-react'

const spanTypeIcons: Record<string, typeof Cpu> = {
  node: Cpu,
  react_iter: Bot,
  llm_call: Bot,
  tool_call: Wrench,
}

const spanStatusColors: Record<string, string> = {
  ok: 'bg-success',
  error: 'bg-destructive',
  fallback: 'bg-warning',
}

const spanTypeLabels: Record<string, string> = {
  node: '工作流节点',
  react_iter: 'ReAct 推理',
  llm_call: 'LLM 调用',
  tool_call: '工具调用',
}

type InferenceStage = {
  key: string
  title: string
  summary: string
  duration: number | null
  width: number
  status: string
  icon: React.ReactNode
}

export function TicketDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: ticket, isLoading } = useTicket(id!)
  const { data: trace } = useTicketTrace(id!)
  const traceDetail = trace as TraceDetail | undefined
  const flatSpans = useMemo(() => flattenSpans(traceDetail?.spans || []), [traceDetail])
  const inferenceStages = useMemo(() => buildInferenceStages(traceDetail), [traceDetail])
  const slowestSpan = flatSpans.reduce<Span | null>((slowest, span) => {
    if (!slowest) return span
    return (span.duration || 0) > (slowest.duration || 0) ? span : slowest
  }, null)
  const llmCalls = flatSpans.filter((span) => span.span_type === 'llm_call').length
  const toolCalls = flatSpans.filter((span) => span.span_type === 'tool_call').length

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
        <div className="col-span-7 space-y-4">
          {/* 基本信息卡片 */}
          <Card className="bg-card border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">工单信息</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-4 gap-4">
                <InfoField label="状态"><StatusBadge status={ticket.status} /></InfoField>
                <InfoField label="分类">{ticket.category ? <CategoryBadge category={ticket.category} /> : '-'}</InfoField>
                <InfoField label="优先级">{ticket.priority ? <PriorityBadge priority={ticket.priority} /> : '-'}</InfoField>
                <InfoField label="重试次数">
                  <span className="text-sm font-mono">{ticket.retry_count} / 3</span>
                </InfoField>
              </div>
              <Separator className="bg-border" />
              <InfoField label="工单内容">
                <p className="text-sm mt-1">{ticket.content}</p>
              </InfoField>
              <Separator className="bg-border" />
              <InfoField label="处理结果">
                <p className="text-sm mt-1 text-foreground/80">
                  {ticket.processing_result || '等待处理...'}
                </p>
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
                        // 用片段前 40 字作为 query 跳转到知识库自动搜索
                        const query = ref.replace(/\s+/g, ' ').trim().slice(0, 40)
                        return (
                          <button
                            key={index}
                            type="button"
                            onClick={() => navigate(`/knowledge?q=${encodeURIComponent(query)}`)}
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
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="max-h-64">
                {messages.length === 0 ? (
                  <p className="text-muted-foreground text-sm text-center py-8">等待处理中...</p>
                ) : (
                  <div className="space-y-2">
                    {messages.map((msg, i) => (
                      <div key={i} className="flex gap-3 p-2 rounded-md bg-background border border-border">
                        <span className="text-xs font-mono text-primary whitespace-nowrap mt-0.5">[{msg.role}]</span>
                        <span className="text-sm text-muted-foreground">{msg.content}</span>
                      </div>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </div>

        {/* 右侧：Trace 链路 */}
        <div className="col-span-5 space-y-4">
          {traceDetail && (
            <>
              <Card className="bg-card border-border">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Brain className="w-4 h-4 text-primary" />
                    Agent 推理总览
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-3">
                    <MiniStat icon={<Clock className="h-4 w-4" />} label="总耗时" value={traceDetail.duration != null ? `${traceDetail.duration.toFixed(2)}s` : '-'} />
                    <MiniStat icon={<Layers className="h-4 w-4" />} label="节点数" value={traceDetail.node_count} />
                    <MiniStat icon={<Bot className="h-4 w-4" />} label="LLM 调用" value={llmCalls} />
                    <MiniStat icon={<Wrench className="h-4 w-4" />} label="工具调用" value={toolCalls} />
                  </div>
                  <div className="mt-3 rounded-md border border-border bg-background p-3 text-xs text-muted-foreground">
                    <span className="text-foreground">最耗时节点：</span>
                    {slowestSpan ? `${slowestSpan.name} · ${formatDuration(slowestSpan.duration)}` : '暂无'}
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-card border-border">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Route className="w-4 h-4 text-primary" />
                    推理阶段
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <InferenceFlow stages={inferenceStages} />
                </CardContent>
              </Card>

              <Card className="bg-card border-border">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Eye className="w-4 h-4 text-primary" />
                    节点证据链
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ScrollArea className="max-h-[520px]">
                    <div className="space-y-2">
                      {traceDetail.spans?.length ? (
                        traceDetail.spans.map((span) => (
                          <SpanNode key={span.span_id} span={span} depth={0} />
                        ))
                      ) : (
                        <p className="text-muted-foreground text-sm text-center py-4">暂无 trace 数据</p>
                      )}
                    </div>
                  </ScrollArea>
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>
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
    <div className="bg-background rounded-md p-2 border border-border">
      <div className="mb-1 text-primary">{icon}</div>
      <p className="text-lg font-bold text-primary">{value}</p>
      <p className="text-[10px] text-muted-foreground">{label}</p>
    </div>
  )
}

function InferenceFlow({ stages }: { stages: InferenceStage[] }) {
  if (stages.length === 0) {
    return <p className="text-muted-foreground text-sm text-center py-4">暂无推理阶段</p>
  }

  return (
    <div className="space-y-3">
      {stages.map((stage, index) => (
        <div key={stage.key} className="relative rounded-lg border border-border bg-background p-3">
          {index < stages.length - 1 && (
            <div className="absolute left-6 top-11 h-8 w-px bg-border" />
          )}
          <div className="flex items-start gap-3">
            <div className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${stage.status === 'error' ? 'bg-destructive/15 text-destructive' : 'bg-primary/15 text-primary'}`}>
              {stage.icon}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium">{stage.title}</p>
                <span className="font-mono text-xs text-muted-foreground">{formatDuration(stage.duration)}</span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{stage.summary}</p>
              <div className="mt-2 h-1.5 rounded bg-muted">
                <div className={`h-full rounded ${stage.status === 'error' ? 'bg-destructive' : 'bg-primary'}`} style={{ width: `${stage.width}%` }} />
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function SpanNode({ span, depth }: { span: Span; depth: number }) {
  const [expanded, setExpanded] = useState(false)
  const Icon = spanTypeIcons[span.span_type] || Cpu
  const statusColor = spanStatusColors[span.status] || 'bg-muted-foreground'
  const hasDetail = span.input_data || span.output_data || span.metadata
  const summary = summarizeSpan(span)

  return (
    <div style={{ paddingLeft: depth * 16 }}>
      <div
        className="flex items-start gap-2 rounded-md bg-background border border-border p-2 text-xs cursor-pointer transition-colors hover:border-primary/50"
        onClick={() => hasDetail && setExpanded(!expanded)}
      >
        {hasDetail ? (
          expanded ? <ChevronDown className="mt-1 w-3 h-3 text-muted-foreground shrink-0" /> : <ChevronRight className="mt-1 w-3 h-3 text-muted-foreground shrink-0" />
        ) : (
          <div className="w-3 shrink-0" />
        )}
        <div className={`mt-1.5 w-2 h-2 rounded-full ${statusColor} shrink-0`} />
        <Icon className="mt-0.5 w-3.5 h-3.5 text-muted-foreground shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium truncate">{span.name}</span>
            <span className="font-mono text-muted-foreground shrink-0">{formatDuration(span.duration)}</span>
          </div>
          <div className="mt-1 flex items-center gap-2">
            <Badge variant="outline" className="border-border bg-card px-1.5 py-0 text-[10px]">
              {spanTypeLabels[span.span_type] || span.span_type}
            </Badge>
            <span className="truncate text-muted-foreground">{summary}</span>
          </div>
        </div>
      </div>
      {expanded && hasDetail && (
        <div className="ml-5 mb-1 rounded-md border border-border bg-background/50 p-2 text-xs space-y-2">
          {span.input_data && (
            <TicketDetailSection icon={<ArrowRightLeft className="w-3 h-3 text-blue-400" />} title="输入" data={span.input_data} />
          )}
          {span.output_data && (
            <TicketDetailSection icon={<FileJson className="w-3 h-3 text-green-400" />} title="输出" data={span.output_data} />
          )}
          {span.metadata && (
            <TicketDetailSection icon={<Info className="w-3 h-3 text-yellow-400" />} title="元数据" data={span.metadata} />
          )}
        </div>
      )}
      {span.children?.map((child) => (
        <SpanNode key={child.span_id} span={child} depth={depth + 1} />
      ))}
    </div>
  )
}

function TicketDetailSection({ icon, title, data }: { icon: React.ReactNode; title: string; data: any }) {
  const [collapsed, setCollapsed] = useState(false)
  const content = typeof data === 'string' ? data : JSON.stringify(data, null, 2)
  const isLong = content.length > 500

  return (
    <div>
      <div className="flex items-center gap-1.5 cursor-pointer select-none" onClick={() => setCollapsed(!collapsed)}>
        {icon}
        <span className="font-medium text-muted-foreground">{title}</span>
        {isLong && (
          collapsed ? <ChevronRight className="w-3 h-3 text-muted-foreground" /> : <ChevronDown className="w-3 h-3 text-muted-foreground" />
        )}
      </div>
      {!collapsed && (
        <pre className="mt-1 p-2 rounded bg-card border border-border overflow-x-auto max-h-64 overflow-y-auto text-[11px] text-foreground/80 whitespace-pre-wrap break-all">
          {isLong ? content.slice(0, 500) + '...' : content}
        </pre>
      )}
    </div>
  )
}

function flattenSpans(spans: Span[]): Span[] {
  return spans.flatMap((span) => [span, ...flattenSpans(span.children || [])])
}

function buildInferenceStages(trace?: TraceDetail): InferenceStage[] {
  if (!trace?.spans?.length) return []
  const flat = flattenSpans(trace.spans)
  const maxDuration = Math.max(...flat.map((span) => span.duration || 0), 0.001)
  const stageNames = ['receive', 'classify', 'process', 'review', 'notify', 'complete']
  const stages = stageNames
    .map((name) => flat.find((span) => span.name === name || span.name.includes(name)))
    .filter((span): span is Span => Boolean(span))

  return stages.map((span) => ({
    key: span.span_id,
    title: stageTitle(span.name),
    summary: summarizeSpan(span),
    duration: span.duration,
    width: Math.max(((span.duration || 0) / maxDuration) * 100, 8),
    status: span.status,
    icon: stageIcon(span.name),
  }))
}

function stageTitle(name: string): string {
  if (name.includes('receive')) return '接收工单'
  if (name.includes('classify')) return '分类与优先级判断'
  if (name.includes('process')) return '方案生成与知识检索'
  if (name.includes('review')) return '结果复核'
  if (name.includes('notify')) return '结果通知'
  if (name.includes('complete')) return '闭环完成'
  return name
}

function stageIcon(name: string): React.ReactNode {
  if (name.includes('receive')) return <MessageSquare className="h-3.5 w-3.5" />
  if (name.includes('classify')) return <Cpu className="h-3.5 w-3.5" />
  if (name.includes('process')) return <Brain className="h-3.5 w-3.5" />
  if (name.includes('review')) return <CheckCircle2 className="h-3.5 w-3.5" />
  if (name.includes('notify')) return <BookOpen className="h-3.5 w-3.5" />
  if (name.includes('complete')) return <CheckCircle2 className="h-3.5 w-3.5" />
  return <Cpu className="h-3.5 w-3.5" />
}

function summarizeSpan(span: Span): string {
  const output = span.output_data || {}
  const input = span.input_data || {}
  const metadata = span.metadata || {}
  const candidates = [
    output.category,
    output.priority,
    output.result,
    output.answer,
    output.final_answer,
    output.processing_result,
    output.review_score != null ? `审核评分 ${output.review_score}` : undefined,
    output.query,
    input.content,
    input.query,
    metadata.tool_name,
    metadata.iteration != null ? `第 ${metadata.iteration} 轮 ReAct` : undefined,
  ]
    .filter((item): item is string | number => item !== undefined && item !== null && item !== '')
    .map(String)

  if (candidates.length > 0) return truncateText(candidates.join(' · '), 60)
  if (span.name.includes('receive')) return '读取用户问题，创建工单状态'
  if (span.name.includes('classify')) return '判断工单类型、优先级和后续处理路径'
  if (span.name.includes('process')) return '结合上下文、知识库和模型推理生成处理方案'
  if (span.name.includes('review')) return '评估处理结果质量，判断是否通过或重试'
  if (span.name.includes('notify')) return '输出处理结果并准备通知用户'
  if (span.name.includes('complete')) return '写入最终状态，完成工单闭环'
  if (span.span_type === 'llm_call') return '大模型生成推理、分类或回复内容'
  if (span.span_type === 'tool_call') return '调用工具补充事实或知识库证据'
  if (span.span_type === 'react_iter') return '执行思考、行动、观察循环'
  return '执行 Agent 工作流节点'
}

function formatDuration(value: number | null | undefined): string {
  if (value == null) return '-'
  if (value < 1) return `${Math.round(value * 1000)}ms`
  return `${value.toFixed(3)}s`
}

function truncateText(value: string, maxLength: number): string {
  return value.length > maxLength ? `${value.slice(0, maxLength)}...` : value
}

function DetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-60" />
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 space-y-4">
          <Skeleton className="h-64 rounded-lg" />
          <Skeleton className="h-48 rounded-lg" />
        </div>
        <div className="space-y-4">
          <Skeleton className="h-32 rounded-lg" />
          <Skeleton className="h-64 rounded-lg" />
        </div>
      </div>
    </div>
  )
}
