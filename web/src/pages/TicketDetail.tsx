import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useTicket, useTicketTrace } from '@/hooks/useApi'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge, CategoryBadge, PriorityBadge } from '@/components/layout/StatusBadge'
import {
  ArrowLeft, Bot, Cpu, Wrench, Eye, MessageSquare,
  ChevronRight, ChevronDown, FileJson, ArrowRightLeft, Info,
} from 'lucide-react'

const spanTypeIcons: Record<string, any> = {
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

export function TicketDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: ticket, isLoading } = useTicket(id!)
  const { data: trace } = useTicketTrace(id!)

  if (isLoading || !ticket) {
    return <DetailSkeleton />
  }

  // 构建消息链
  const messages: { role: string; content: string }[] = []
  if (ticket.status) messages.push({ role: 'system', content: `工单创建，状态: ${ticket.status}` })
  if (ticket.category) messages.push({ role: 'classifier', content: `分类结果: ${ticket.category} | 优先级: ${ticket.priority || '-'}` })
  if (ticket.processing_result) messages.push({ role: 'processor', content: ticket.processing_result })
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

      <div className="grid grid-cols-3 gap-6">
        {/* 左侧：基本信息 + 消息链 */}
        <div className="col-span-2 space-y-4">
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
        <div className="space-y-4">
          {trace && (
            <>
              {/* Trace 统计 */}
              <Card className="bg-card border-border">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Eye className="w-4 h-4 text-primary" />
                    执行追踪
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-3">
                    <MiniStat label="耗时" value={trace.duration != null ? `${trace.duration.toFixed(2)}s` : '-'} />
                    <MiniStat label="节点数" value={trace.node_count} />
                    <MiniStat label="LLM 调用" value={trace.total_tokens} />
                    <MiniStat label="工具调用" value={trace.total_tool_calls} />
                  </div>
                </CardContent>
              </Card>

              {/* Span 时间线 */}
              <Card className="bg-card border-border">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">执行链路</CardTitle>
                </CardHeader>
                <CardContent>
                  <ScrollArea className="max-h-96">
                    {trace.spans?.length ? (
                      <div className="space-y-1.5">
                        {trace.spans.map((span: any) => (
                          <SpanNode key={span.span_id} span={span} depth={0} />
                        ))}
                      </div>
                    ) : (
                      <p className="text-muted-foreground text-sm text-center py-4">暂无 trace 数据</p>
                    )}
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

function MiniStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-background rounded-md p-2 border border-border">
      <p className="text-lg font-bold text-primary">{value}</p>
      <p className="text-[10px] text-muted-foreground">{label}</p>
    </div>
  )
}

function SpanNode({ span, depth }: { span: any; depth: number }) {
  const [expanded, setExpanded] = useState(false)
  const Icon = spanTypeIcons[span.span_type] || Cpu
  const statusColor = spanStatusColors[span.status] || 'bg-muted-foreground'
  const hasDetail = span.input_data || span.output_data || span.metadata

  return (
    <div style={{ paddingLeft: depth * 16 }}>
      <div
        className={`flex items-center gap-2 p-2 rounded-md bg-background border border-border text-xs cursor-pointer transition-colors hover:border-primary/50`}
        onClick={() => hasDetail && setExpanded(!expanded)}
      >
        {hasDetail ? (
          expanded ? <ChevronDown className="w-3 h-3 text-muted-foreground shrink-0" /> : <ChevronRight className="w-3 h-3 text-muted-foreground shrink-0" />
        ) : (
          <div className="w-3 shrink-0" />
        )}
        <div className={`w-2 h-2 rounded-full ${statusColor} shrink-0`} />
        <Icon className="w-3 h-3 text-muted-foreground shrink-0" />
        <span className="font-medium truncate flex-1">{span.name}</span>
        <span className="font-mono text-muted-foreground shrink-0">
          {span.duration != null ? `${span.duration.toFixed(3)}s` : '-'}
        </span>
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
      {span.children?.map((child: any) => (
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
