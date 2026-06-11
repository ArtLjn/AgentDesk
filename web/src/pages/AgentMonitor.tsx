import { useState } from 'react'
import { useTraces } from '@/hooks/useApi'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Activity, RefreshCw, Clock, Cpu, Bot, Wrench, Zap, ArrowDownUp,
  ChevronRight, ChevronDown, FileJson, ArrowRightLeft, Info,
} from 'lucide-react'

const traceStatusStyles: Record<string, string> = {
  running: 'bg-primary/15 text-primary',
  completed: 'bg-success/15 text-success',
  failed: 'bg-destructive/15 text-destructive',
}

const spanStatusDot: Record<string, string> = {
  ok: 'bg-success',
  error: 'bg-destructive',
  fallback: 'bg-warning',
}

export function AgentMonitor() {
  const [selectedTraceId, setSelectedTraceId] = useState<string>('')
  const { data: tracesData, isLoading, refetch } = useTraces()
  const [selectedTraceDetail, setSelectedTraceDetail] = useState<any>(null)

  const traces = tracesData?.traces || []

  // 当选中 trace 时，获取详情
  const fetchTraceDetail = async (_traceId: string, ticketId: string) => {
    try {
      const res = await fetch(`/api/tickets/${ticketId}/trace`)
      if (res.ok) {
        const data = await res.json()
        setSelectedTraceDetail(data)
      }
    } catch {
      setSelectedTraceDetail(null)
    }
  }

  const handleTraceClick = (trace: any) => {
    setSelectedTraceId(trace.trace_id)
    fetchTraceDetail(trace.trace_id, trace.ticket_id)
  }

  // 最慢 span 排行
  const flatSpans = (selectedTraceDetail?.spans || []).flatMap(function flatten(s: any): any[] {
    return [s, ...(s.children || []).flatMap(flatten)]
  })
  const slowestSpans = [...flatSpans].sort((a, b) => (b.duration || 0) - (a.duration || 0)).slice(0, 5)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Activity className="w-5 h-5 text-primary" />
            Agent 监控
          </h2>
          <p className="text-sm text-muted-foreground mt-1">执行追踪与性能分析</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="w-3.5 h-3.5 mr-1" />
          刷新
        </Button>
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* Trace 列表 */}
        <div className="col-span-4">
          <Card className="bg-card border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Trace 列表</CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[600px]">
                {isLoading ? (
                  <div className="space-y-2">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Skeleton key={i} className="h-16 rounded-md" />
                    ))}
                  </div>
                ) : traces.length === 0 ? (
                  <p className="text-muted-foreground text-sm text-center py-12">暂无 trace 数据</p>
                ) : (
                  <div className="space-y-2">
                    {traces.map((trace: any) => (
                      <div
                        key={trace.trace_id}
                        onClick={() => handleTraceClick(trace)}
                        className={`p-3 rounded-md border cursor-pointer transition-colors ${
                          selectedTraceId === trace.trace_id
                            ? 'border-primary bg-primary/5'
                            : 'border-border bg-background hover:border-primary/50'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="font-mono text-xs text-primary">{trace.trace_id?.slice(0, 20)}</span>
                          <Badge variant="outline" className={`border-0 text-[10px] ${traceStatusStyles[trace.status] || ''}`}>
                            {trace.status}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                          <span>{trace.ticket_id?.slice(0, 12)}</span>
                          <span className="flex items-center gap-1"><Cpu className="w-3 h-3" />{trace.node_count || 0}</span>
                          <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{trace.duration != null ? `${trace.duration.toFixed(2)}s` : '-'}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </div>

        {/* Trace 详情 */}
        <div className="col-span-8 space-y-4">
          {!selectedTraceDetail ? (
            <Card className="bg-card border-border">
              <CardContent className="py-20 text-center text-muted-foreground text-sm">
                点击左侧 trace 查看执行链路
              </CardContent>
            </Card>
          ) : (
            <>
              {/* 统计条 */}
              <Card className="bg-card border-border">
                <CardContent className="p-3">
                  <div className="flex gap-6">
                    <StatItem label="状态" value={selectedTraceDetail.status} />
                    <StatItem label="总耗时" value={selectedTraceDetail.duration != null ? `${selectedTraceDetail.duration.toFixed(2)}s` : '-'} />
                    <StatItem label="节点数" value={selectedTraceDetail.node_count || 0} />
                    <StatItem label="LLM Token" value={selectedTraceDetail.total_tokens || 0} />
                    <StatItem label="工具调用" value={selectedTraceDetail.total_tool_calls || 0} />
                  </div>
                </CardContent>
              </Card>

              <div className="grid grid-cols-5 gap-4">
                {/* 执行链路 */}
                <div className="col-span-3">
                  <Card className="bg-card border-border">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-sm">执行链路</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ScrollArea className="h-[480px]">
                        <div className="space-y-1.5">
                          {(selectedTraceDetail.spans || []).map((span: any) => (
                            <SpanTree key={span.span_id} span={span} depth={0} />
                          ))}
                        </div>
                      </ScrollArea>
                    </CardContent>
                  </Card>
                </div>

                {/* 最慢 Span */}
                <div className="col-span-2">
                  <Card className="bg-card border-border">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-sm flex items-center gap-2">
                        <ArrowDownUp className="w-4 h-4 text-warning" />
                        最慢 Span
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {slowestSpans.map((span: any, i: number) => (
                          <div key={span.span_id} className="flex items-center justify-between p-2 rounded-md bg-background border border-border text-xs">
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="text-muted-foreground w-4">{i + 1}</span>
                              <span className="truncate">{span.name}</span>
                              <Badge variant="outline" className="border-0 text-[10px] bg-secondary">
                                {span.span_type}
                              </Badge>
                            </div>
                            <span className="font-mono text-destructive shrink-0 ml-2">
                              {span.duration != null ? `${span.duration.toFixed(3)}s` : '-'}
                            </span>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function StatItem({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="text-center">
      <p className="text-lg font-bold text-primary">{value}</p>
      <p className="text-[10px] text-muted-foreground">{label}</p>
    </div>
  )
}

function SpanTree({ span, depth }: { span: any; depth: number }) {
  const [expanded, setExpanded] = useState(false)
  const typeIcons: Record<string, any> = { node: Cpu, react_iter: Bot, llm_call: Zap, tool_call: Wrench }
  const Icon = typeIcons[span.span_type] || Cpu
  const dot = spanStatusDot[span.status] || 'bg-muted-foreground'
  const hasDetail = span.input_data || span.output_data || span.metadata

  return (
    <div style={{ paddingLeft: depth * 16 }}>
      <div
        className={`flex items-center gap-2 p-2 rounded-md bg-background border border-border text-xs mb-1 cursor-pointer transition-colors hover:border-primary/50 ${hasDetail ? '' : ''}`}
        onClick={() => hasDetail && setExpanded(!expanded)}
      >
        {hasDetail ? (
          expanded ? <ChevronDown className="w-3 h-3 text-muted-foreground shrink-0" /> : <ChevronRight className="w-3 h-3 text-muted-foreground shrink-0" />
        ) : (
          <div className="w-3 shrink-0" />
        )}
        <div className={`w-2 h-2 rounded-full ${dot} shrink-0`} />
        <Icon className="w-3 h-3 text-muted-foreground shrink-0" />
        <div className="flex-1 min-w-0">
          <span className="font-medium">{span.name}</span>
          <span className="text-muted-foreground ml-2">{span.span_type}</span>
          {span.status !== 'ok' && <span className="text-warning ml-1">({span.status})</span>}
        </div>
        <span className="font-mono text-muted-foreground shrink-0">
          {span.duration != null ? `${span.duration.toFixed(3)}s` : '-'}
        </span>
      </div>
      {expanded && hasDetail && (
        <div className="ml-5 mb-1 rounded-md border border-border bg-background/50 p-2 text-xs space-y-2">
          {span.input_data && (
            <DetailSection icon={<ArrowRightLeft className="w-3 h-3 text-blue-400" />} title="输入" data={span.input_data} />
          )}
          {span.output_data && (
            <DetailSection icon={<FileJson className="w-3 h-3 text-green-400" />} title="输出" data={span.output_data} />
          )}
          {span.metadata && (
            <DetailSection icon={<Info className="w-3 h-3 text-yellow-400" />} title="元数据" data={span.metadata} />
          )}
        </div>
      )}
      {span.children?.map((child: any) => (
        <SpanTree key={child.span_id} span={child} depth={depth + 1} />
      ))}
    </div>
  )
}

function DetailSection({ icon, title, data }: { icon: React.ReactNode; title: string; data: any }) {
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
          {isLong && !collapsed ? content.slice(0, 500) + '...' : content}
        </pre>
      )}
    </div>
  )
}
