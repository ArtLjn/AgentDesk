/**
 * 实时执行流：在工单详情页展示 agent 实时工作过程。
 *
 * 数据来源：
 *  - 初始：从 trace.spans 拉取已完成节点
 *  - 实时：订阅 /ws/monitor WebSocket，过滤本工单事件追加
 *  - trace 在工单运行中自动 refetch（useTicketTrace(isRunning)）
 *
 * 渲染：垂直时间线，每个父节点可展开查看子 span（LLM 推理 / 工具调用 / ReAct 思考）。
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Loader2, CheckCircle2, AlertCircle, Route, Brain, MessageSquare,
  Wrench, Zap, UserCheck, GitBranch, Cpu, ChevronDown, ChevronRight,
  SearchCheck, FileCheck2, ArrowRight,
} from 'lucide-react'
import type { Span, WSMessage } from '@/types'
import { useWebSocket } from '@/hooks/useWebSocket'
import { Markdown } from '@/components/ui/markdown'

const NODE_STYLE: Record<string, { label: string; color: string; bg: string; icon: React.ReactNode }> = {
  receive: { label: '接收工单', color: '#1890ff', bg: 'rgba(24,144,255,0.10)', icon: <MessageSquare className="h-3.5 w-3.5" /> },
  classify: { label: '智能分类', color: '#722ed1', bg: 'rgba(114,46,209,0.10)', icon: <Route className="h-3.5 w-3.5" /> },
  route: { label: '路由决策', color: '#722ed1', bg: 'rgba(114,46,209,0.10)', icon: <GitBranch className="h-3.5 w-3.5" /> },
  process: { label: '工单处理', color: '#13c2c2', bg: 'rgba(19,194,194,0.10)', icon: <Cpu className="h-3.5 w-3.5" /> },
  review: { label: '质量审核', color: '#13c2c2', bg: 'rgba(19,194,194,0.10)', icon: <CheckCircle2 className="h-3.5 w-3.5" /> },
  retry_check: { label: '重试检查', color: '#faad14', bg: 'rgba(250,173,20,0.12)', icon: <AlertCircle className="h-3.5 w-3.5" /> },
  auto_reply: { label: '自动回复', color: '#1890ff', bg: 'rgba(24,144,255,0.10)', icon: <MessageSquare className="h-3.5 w-3.5" /> },
  escalate: { label: '升级处理', color: '#faad14', bg: 'rgba(250,173,20,0.12)', icon: <AlertCircle className="h-3.5 w-3.5" /> },
  notify: { label: '发送通知', color: '#52c41a', bg: 'rgba(82,196,26,0.10)', icon: <CheckCircle2 className="h-3.5 w-3.5" /> },
  complete: { label: '归档完成', color: '#52c41a', bg: 'rgba(82,196,26,0.10)', icon: <CheckCircle2 className="h-3.5 w-3.5" /> },
  handle_failure: { label: '失败处理', color: '#ff4d4f', bg: 'rgba(255,77,79,0.10)', icon: <AlertCircle className="h-3.5 w-3.5" /> },
  human_review_wait: { label: '等待人工审核', color: '#ff4d4f', bg: 'rgba(255,77,79,0.10)', icon: <UserCheck className="h-3.5 w-3.5" /> },
  apply_human_decision: { label: '人工决策恢复', color: '#ff4d4f', bg: 'rgba(255,77,79,0.10)', icon: <UserCheck className="h-3.5 w-3.5" /> },
  llm_call: { label: 'LLM 推理', color: '#13c2c2', bg: 'rgba(19,194,194,0.10)', icon: <Zap className="h-3 w-3" /> },
  tool_call: { label: '工具调用', color: '#52c41a', bg: 'rgba(82,196,26,0.10)', icon: <Wrench className="h-3 w-3" /> },
  react_iter: { label: 'ReAct 推理', color: '#722ed1', bg: 'rgba(114,46,209,0.10)', icon: <Brain className="h-3 w-3" /> },
  memory_call: { label: '记忆加载', color: '#1890ff', bg: 'rgba(24,144,255,0.10)', icon: <Brain className="h-3 w-3" /> },
}

function getStyle(node: string, spanType?: string) {
  const key = node || spanType || ''
  return NODE_STYLE[key] ?? {
    label: node || spanType || '节点',
    color: '#8b949e',
    bg: 'rgba(139,148,158,0.12)',
    icon: <Cpu className="h-3 w-3" />,
  }
}

interface FlowEvent {
  key: string
  node: string
  spanType?: string
  message?: string
  status: string
  duration?: number | null
  timestamp: number
  isError?: boolean
  children: Span[]
  rawSpan?: Span
}

interface LiveExecutionFlowProps {
  ticketId: string
  spans: Span[]
  isRunning: boolean
}

interface ReasoningStats {
  thoughts: number
  tools: number
  knowledgeHits: number
  finalAnswers: number
}

export function LiveExecutionFlow({ ticketId, spans, isRunning }: LiveExecutionFlowProps) {
  const [liveEvents, setLiveEvents] = useState<FlowEvent[]>([])
  const [manualExpanded, setManualExpanded] = useState<Set<string>>(new Set())
  const [manualCollapsed, setManualCollapsed] = useState<Set<string>>(new Set())
  const seenKeys = useRef<Set<string>>(new Set())
  const scrollRef = useRef<HTMLDivElement | null>(null)

  const initialEvents = useMemo<FlowEvent[]>(() => {
    return spans
      .filter((s) => s.span_type === 'node')
      .map((s) => ({
        key: s.span_id,
        node: s.name,
        spanType: s.span_type,
        status: s.status,
        duration: s.duration,
        timestamp: s.start_time || 0,
        isError: s.status === 'error',
        children: s.children || [],
        rawSpan: s,
      }))
      .sort((a, b) => a.timestamp - b.timestamp)
  }, [spans])

  useEffect(() => {
    initialEvents.forEach((e) => seenKeys.current.add(e.key))
  }, [initialEvents])

  useWebSocket((msg: WSMessage) => {
    if (msg.ticket_id !== ticketId || !msg.node) return
    if (msg.node === 'error') return

    const data = (msg.data || {}) as Record<string, unknown>
    const span = (data.span || {}) as Partial<Span>
    const spanId = span.span_id || (data.span_id as string) || `${msg.node}-${msg.timestamp}`
    if (seenKeys.current.has(spanId)) return
    seenKeys.current.add(spanId)

    const event: FlowEvent = {
      key: spanId,
      node: span.name || msg.node,
      spanType: span.span_type || (data.span_type as string | undefined),
      message: msg.message,
      status: span.status || (data.status as string) || 'ok',
      duration: span.duration ?? (data.duration as number | undefined),
      timestamp: new Date(msg.timestamp).getTime() / 1000,
      isError: msg.status === 'failed' || span.status === 'error' || data.status === 'error',
      children: [],
    }
    setLiveEvents((prev) => [...prev, event])
  })

  const merged = useMemo(() => {
    const map = new Map<string, FlowEvent>()
    ;[...initialEvents, ...liveEvents].forEach((e) => map.set(e.key, e))
    return Array.from(map.values()).sort((a, b) => a.timestamp - b.timestamp)
  }, [initialEvents, liveEvents])
  const totalReasoningStats = useMemo(() => {
    return merged.reduce(
      (acc, event) => mergeReasoningStats(acc, getReasoningStats(event.children)),
      emptyReasoningStats(),
    )
  }, [merged])

  const latestEvent = merged.at(-1)
  const latestEventKey = latestEvent?.key
  const latestEventChildrenLength = latestEvent?.children.length ?? 0

  const expanded = useMemo(() => {
    const next = new Set(manualExpanded)
    if (latestEventKey && latestEventChildrenLength > 0 && !manualCollapsed.has(latestEventKey)) {
      next.add(latestEventKey)
    }
    return next
  }, [latestEventKey, latestEventChildrenLength, manualCollapsed, manualExpanded])

  useEffect(() => {
    if (!latestEventKey || !scrollRef.current) return

    const timer = window.setTimeout(() => {
      scrollRef.current?.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: 'smooth',
      })
    }, 80)

    return () => window.clearTimeout(timer)
  }, [expanded, latestEventKey])

  const toggleExpand = (key: string) => {
    if (key === latestEventKey) {
      setManualCollapsed((prev) => {
        const next = new Set(prev)
        if (expanded.has(key)) {
          next.add(key)
        } else {
          next.delete(key)
        }
        return next
      })
      return
    }

    setManualExpanded((prev) => {
      const next = new Set(prev)
      if (expanded.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  if (merged.length === 0 && !isRunning) {
    return null
  }

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="flex items-center gap-2 border-b border-border bg-primary/5 px-4 py-2.5">
        {isRunning ? (
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
        ) : (
          <CheckCircle2 className="h-4 w-4 text-success" />
        )}
        <span className="text-sm font-medium">
          {isRunning ? 'Agent 正在工作' : '执行完成'}
        </span>
        <span className="ml-auto text-[11px] text-muted-foreground">
          {merged.length} 个节点 · 总展开 {expanded.size}
        </span>
      </div>
      <ReasoningPulse stats={totalReasoningStats} isRunning={isRunning} />

      <div ref={scrollRef} className="max-h-[640px] overflow-y-auto p-3">
        <ol className="relative space-y-2 before:absolute before:left-[15px] before:top-2 before:bottom-2 before:w-px before:bg-border">
          {merged.map((event, idx) => {
            const style = getStyle(event.node, event.spanType)
            const isLast = idx === merged.length - 1
            const isRunningNode = isLast && isRunning
            const hasChildren = event.children.length > 0
            const isExpanded = expanded.has(event.key)
            const reasoningStats = getReasoningStats(event.children)
            return (
              <li
                key={event.key}
                className="relative pl-10 animate-in fade-in slide-in-from-bottom-2 duration-300"
              >
                <span
                  className={`absolute left-0 top-0.5 flex h-8 w-8 items-center justify-center rounded-full border-2 bg-card ${
                    isRunningNode ? 'animate-pulse' : ''
                  }`}
                  style={{
                    borderColor: style.color,
                    color: style.color,
                    backgroundColor: isRunningNode ? style.bg : undefined,
                  }}
                >
                  {isRunningNode ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : event.isError ? (
                    <AlertCircle className="h-3.5 w-3.5 text-destructive" />
                  ) : (
                    style.icon
                  )}
                </span>

                <div
                  className={`rounded-md border transition-colors ${
                    event.isError
                      ? 'border-destructive/40 bg-destructive/5'
                      : isRunningNode
                      ? 'border-primary/50 bg-primary/5'
                      : 'border-border bg-background'
                  }`}
                >
                  <button
                    type="button"
                    disabled={!hasChildren}
                    onClick={() => toggleExpand(event.key)}
                    className={`flex w-full items-center gap-2 px-2.5 py-2 text-left ${
                      hasChildren ? 'cursor-pointer hover:bg-muted/30' : 'cursor-default'
                    }`}
                  >
                    {hasChildren && (
                      <span className="text-muted-foreground">
                        {isExpanded
                          ? <ChevronDown className="h-3 w-3" />
                          : <ChevronRight className="h-3 w-3" />}
                      </span>
                    )}
                    <span
                      className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium"
                      style={{ backgroundColor: style.bg, color: style.color }}
                    >
                      {style.icon}
                      {style.label}
                    </span>
                    {event.duration != null && event.duration > 0 && (
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {event.duration < 1
                          ? `${Math.round(event.duration * 1000)}ms`
                          : `${event.duration.toFixed(2)}s`}
                      </span>
                    )}
                    {hasChildren && (
                      <span className="text-[10px] text-muted-foreground/70">
                        · {event.children.length} 步
                      </span>
                    )}
                    <ReasoningBadges stats={reasoningStats} />
                    {isRunningNode && (
                      <span className="ml-auto text-[10px] text-primary font-medium animate-pulse">
                        进行中...
                      </span>
                    )}
                  </button>

                  {event.message && !hasChildren && (
                    <div className="px-2.5 pb-2 -mt-1">
                      <p className="text-xs text-foreground/80 leading-relaxed">{event.message}</p>
                    </div>
                  )}

                  {event.rawSpan && (
                    <NodeCollaborationPanel span={event.rawSpan} />
                  )}

                  {hasChildren && isExpanded && (
                    <div className="border-t border-border/60 px-2.5 py-2 space-y-1.5 animate-in fade-in slide-in-from-top-1 duration-200">
                      {event.children.map((child) => (
                        <ChildSpanView key={child.span_id} span={child} />
                      ))}
                    </div>
                  )}
                </div>
              </li>
            )
          })}

          {isRunning && merged.length === 0 && (
            <li className="relative pl-10 animate-in fade-in duration-300">
              <span className="absolute left-0 top-0.5 flex h-8 w-8 items-center justify-center rounded-full border-2 border-primary bg-primary/5">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
              </span>
              <div className="rounded-md border border-primary/30 bg-primary/5 p-2.5">
                <p className="text-xs text-primary">正在初始化工作流...</p>
              </div>
            </li>
          )}
        </ol>
      </div>
    </div>
  )
}

function NodeCollaborationPanel({ span }: { span: Span }) {
  const handoff = extractAgentHandoff(span)
  const quality = extractQualityReview(span)

  if (!handoff && !quality) return null

  return (
    <div className="border-t border-border/60 bg-background/40 px-2.5 py-2">
      {handoff && (
        <div className="mb-2 rounded border border-primary/20 bg-primary/5 px-2.5 py-2">
          <div className="flex flex-wrap items-center gap-2 text-[10px] font-medium text-primary">
            <span>{handoff.fromAgent}</span>
            <ArrowRight className="h-3 w-3" />
            <span>{handoff.toAgent}</span>
            <span className="rounded bg-background/70 px-1.5 py-0.5 text-muted-foreground">
              {handoff.artifact}
            </span>
          </div>
          {handoff.summary && (
            <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-foreground/80">
              {handoff.summary}
            </p>
          )}
        </div>
      )}

      {quality && (
        <div className="rounded border border-success/25 bg-success/5 px-2.5 py-2">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-wide text-success">
              Reviewer 质量门禁
            </span>
            <span className="rounded bg-background/70 px-1.5 py-0.5 font-mono text-[10px] text-foreground">
              {quality.score.toFixed(2)}
            </span>
            {quality.shouldRetry && (
              <span className="rounded border border-warning/30 bg-warning/10 px-1.5 py-0.5 text-[10px] text-warning">
                打回返工
              </span>
            )}
          </div>
          <div className="grid gap-1.5 sm:grid-cols-4">
            {quality.dimensions.map((item) => (
              <div key={item.key} className="rounded border border-border/70 bg-background/60 px-2 py-1.5">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="text-[10px] text-muted-foreground">{item.label}</span>
                  <span className="font-mono text-[10px] text-foreground">{item.value.toFixed(2)}</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-success"
                    style={{ width: `${Math.round((item.value / item.max) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
          {(quality.issues.length > 0 || quality.suggestion) && (
            <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
              <InsightPreview
                item={{
                  key: 'quality_issues',
                  label: '发现问题',
                  value: quality.issues.length > 0 ? quality.issues.join('；') : '未发现阻断问题',
                  tone: quality.issues.length > 0 ? 'warning' : 'success',
                }}
              />
              {quality.suggestion && (
                <InsightPreview
                  item={{
                    key: 'quality_suggestion',
                    label: '改进建议',
                    value: quality.suggestion,
                    tone: 'primary',
                  }}
                />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ReasoningPulse({ stats, isRunning }: { stats: ReasoningStats; isRunning: boolean }) {
  const items = [
    { key: 'thoughts', label: '思考', value: stats.thoughts, icon: <Brain className="h-3 w-3" />, tone: 'text-primary' },
    { key: 'tools', label: '工具', value: stats.tools, icon: <Wrench className="h-3 w-3" />, tone: 'text-success' },
    { key: 'knowledge', label: '知识命中', value: stats.knowledgeHits, icon: <SearchCheck className="h-3 w-3" />, tone: 'text-warning' },
    { key: 'answers', label: '结论', value: stats.finalAnswers, icon: <FileCheck2 className="h-3 w-3" />, tone: 'text-primary' },
  ]

  return (
    <div className="border-b border-border bg-background/40 px-4 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          推理信号
        </span>
        {items.map((item) => (
          <span
            key={item.key}
            className="inline-flex items-center gap-1 rounded border border-border bg-card/70 px-2 py-1 text-[10px] text-muted-foreground"
          >
            <span className={item.tone}>{item.icon}</span>
            <span>{item.label}</span>
            <span className="font-mono text-foreground">{item.value}</span>
          </span>
        ))}
        {isRunning && (
          <span className="ml-auto inline-flex items-center gap-1 text-[10px] text-primary">
            <Loader2 className="h-3 w-3 animate-spin" />
            正在推理
          </span>
        )}
      </div>
    </div>
  )
}

function ReasoningBadges({ stats }: { stats: ReasoningStats }) {
  const chips = [
    stats.thoughts > 0 ? { label: `思考 ${stats.thoughts}`, className: 'border-primary/30 bg-primary/5 text-primary' } : null,
    stats.tools > 0 ? { label: `工具 ${stats.tools}`, className: 'border-success/30 bg-success/5 text-success' } : null,
    stats.knowledgeHits > 0 ? { label: `知识 ${stats.knowledgeHits}`, className: 'border-warning/30 bg-warning/5 text-warning' } : null,
    stats.finalAnswers > 0 ? { label: `结论 ${stats.finalAnswers}`, className: 'border-primary/30 bg-primary/5 text-primary' } : null,
  ].filter(Boolean) as { label: string; className: string }[]

  if (chips.length === 0) return null

  return (
    <span className="ml-auto flex items-center gap-1">
      {chips.map((chip) => (
        <span key={chip.label} className={`rounded border px-1.5 py-0.5 text-[9px] font-medium ${chip.className}`}>
          {chip.label}
        </span>
      ))}
    </span>
  )
}

/** 子 span（llm_call / tool_call / react_iter）的渲染 */
function ChildSpanView({ span }: { span: Span }) {
  const style = getStyle(span.name, span.span_type)
  const summary = summarizeChildOutput(span)
  const highlights = extractSpanHighlights(span)
  const detailContent = extractMarkdownFromSpan(span)
  const ragDocs = extractRagDocs(span)
  const rawPayload = span.output_data || span.input_data || span.metadata || {}
  const hasRawPayload = rawPayload && Object.keys(rawPayload).length > 0

  // RAG 检索：默认展开显示文档列表（最有价值的细节）
  const isRagWithDocs = span.span_type === 'tool_call' && ragDocs.length > 0
  const hasDetail = highlights.length > 0 || !!detailContent || hasRawPayload || isRagWithDocs
  const [showDetail, setShowDetail] = useState(
    span.span_type === 'react_iter' && highlights.length > 0,
  )
  const [showRagDocs, setShowRagDocs] = useState(isRagWithDocs)

  return (
    <div className="rounded border border-border/70 bg-background/60 overflow-hidden">
      <button
        type="button"
        onClick={() => hasDetail && setShowDetail(!showDetail)}
        className={`flex w-full items-center gap-2 px-2 py-1.5 text-left ${
          hasDetail ? 'hover:bg-muted/40 cursor-pointer' : 'cursor-default'
        }`}
      >
        <span
          className="inline-flex h-5 w-5 items-center justify-center rounded"
          style={{ backgroundColor: style.bg, color: style.color }}
        >
          {style.icon}
        </span>
        <span className="text-[11px] font-medium text-foreground/90">{style.label}</span>
        {span.duration != null && span.duration > 0 && (
          <span className="font-mono text-[10px] text-muted-foreground">
            {span.duration < 1
              ? `${Math.round(span.duration * 1000)}ms`
              : `${span.duration.toFixed(2)}s`}
          </span>
        )}
        {hasDetail && (
          <span className="ml-auto text-muted-foreground">
            {showDetail
              ? <ChevronDown className="h-3 w-3" />
              : <ChevronRight className="h-3 w-3" />}
          </span>
        )}
      </button>

      {summary.text && (
        <div className="px-2 pb-1.5 -mt-0.5">
          <p className={`text-[11px] text-muted-foreground leading-relaxed ${showDetail ? '' : 'line-clamp-3'}`}>
            {summary.text}
          </p>
        </div>
      )}

      {highlights.length > 0 && !showDetail && (
        <div className="grid gap-1.5 px-2 pb-2 sm:grid-cols-2">
          {highlights.slice(0, 2).map((item) => (
            <InsightPreview key={item.key} item={item} />
          ))}
        </div>
      )}

      {showDetail && highlights.length > 0 && (
        <div className="border-t border-border/60 bg-background px-2 py-2">
          <div className="grid gap-2">
            {highlights.map((item) => (
              <InsightBlock key={item.key} item={item} />
            ))}
          </div>
        </div>
      )}

      {/* RAG 检索文档列表 */}
      {isRagWithDocs && (
        <div className="border-t border-border/60 bg-background/40">
          <button
            type="button"
            onClick={() => setShowRagDocs(!showRagDocs)}
            className="flex w-full items-center gap-1.5 px-2 py-1.5 text-left hover:bg-muted/30"
          >
            {showRagDocs
              ? <ChevronDown className="h-3 w-3 text-muted-foreground" />
              : <ChevronRight className="h-3 w-3 text-muted-foreground" />}
            <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">
              检索到的知识片段
            </span>
            <span className="ml-auto text-[10px] text-muted-foreground">{ragDocs.length} 条</span>
          </button>
          {showRagDocs && (
            <ul className="px-2 pb-2 space-y-1 animate-in fade-in duration-200">
              {ragDocs.map((doc, i) => (
                <li key={i} className="rounded border border-border/60 bg-background p-1.5">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="font-mono text-[10px] text-muted-foreground">#{i + 1}</span>
                    <span className="text-[11px] font-medium text-foreground truncate flex-1">
                      {doc.title}
                    </span>
                    <span
                      className="rounded px-1 py-0.5 text-[9px] font-mono"
                      style={{
                        backgroundColor: scoreColor(doc.score),
                        color: '#fff',
                      }}
                    >
                      {doc.score.toFixed(3)}
                    </span>
                  </div>
                  {doc.category && (
                    <span className="inline-block rounded bg-muted/60 px-1.5 py-0.5 text-[9px] text-muted-foreground mr-1 mb-0.5">
                      {doc.category}
                    </span>
                  )}
                  {doc.preview && (
                    <p className="text-[10px] text-muted-foreground leading-relaxed line-clamp-2 mt-0.5">
                      {doc.preview}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {showDetail && detailContent && (
        <div className="border-t border-border/60 px-2 py-2 bg-background">
          <Markdown>{detailContent}</Markdown>
        </div>
      )}

      {showDetail && hasRawPayload && (
        <div className="border-t border-border/60 px-2 py-2 bg-background">
          <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            原始 Trace 数据
          </div>
          <pre className="text-[10px] text-muted-foreground whitespace-pre-wrap break-all">
            {JSON.stringify(rawPayload, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

interface RagDoc {
  title: string
  category: string
  score: number
  preview: string
}

interface AgentHandoff {
  fromAgent: string
  toAgent: string
  artifact: string
  summary: string
}

interface QualityDimension {
  key: string
  label: string
  value: number
  max: number
}

interface QualityReview {
  score: number
  dimensions: QualityDimension[]
  issues: string[]
  suggestion: string
  shouldRetry: boolean
}

function extractRagDocs(span: Span): RagDoc[] {
  const meta = (span.metadata || {}) as Record<string, unknown>
  const ragStats = meta.rag_stats as Record<string, unknown> | undefined
  if (!ragStats) return []
  const docs = ragStats.retrieved_docs as RagDoc[] | undefined
  if (!Array.isArray(docs)) return []
  return docs.filter((d) => typeof d.score === 'number')
}

function scoreColor(score: number): string {
  if (score >= 0.7) return '#52c41a'
  if (score >= 0.5) return '#1890ff'
  if (score >= 0.35) return '#faad14'
  return '#ff4d4f'
}

function extractAgentHandoff(span: Span): AgentHandoff | null {
  const meta = (span.metadata || {}) as Record<string, unknown>
  const raw = meta.agent_handoff
  if (!raw || typeof raw !== 'object') return null
  const handoff = raw as Record<string, unknown>
  const fromAgent = pickString(handoff.from_agent, handoff.fromAgent)
  const toAgent = pickString(handoff.to_agent, handoff.toAgent)
  if (!fromAgent || !toAgent) return null
  return {
    fromAgent,
    toAgent,
    artifact: pickString(handoff.artifact) || '协作交接',
    summary: pickString(handoff.summary) || '',
  }
}

function extractQualityReview(span: Span): QualityReview | null {
  if (span.name !== 'review') return null
  const out = (span.output_data || {}) as Record<string, unknown>
  const score = typeof out.review_score === 'number' ? out.review_score : null
  if (score == null) return null

  const rawDimensions = out.dimensions && typeof out.dimensions === 'object'
    ? out.dimensions as Record<string, unknown>
    : {}
  const specs = [
    { key: 'accuracy', label: '准确性', max: 0.3 },
    { key: 'feasibility', label: '可行性', max: 0.3 },
    { key: 'completeness', label: '完整性', max: 0.2 },
    { key: 'professionalism', label: '专业性', max: 0.2 },
  ]
  const dimensions = specs.map((spec) => ({
    ...spec,
    value: clampNumber(rawDimensions[spec.key], 0, spec.max),
  }))
  const rawIssues = Array.isArray(out.issues) ? out.issues : []
  return {
    score,
    dimensions,
    issues: rawIssues.map((issue) => String(issue)).filter(Boolean),
    suggestion: pickString(out.suggestion, out.feedback) || '',
    shouldRetry: Boolean(out.should_retry),
  }
}

function clampNumber(value: unknown, min: number, max: number): number {
  if (typeof value !== 'number' || Number.isNaN(value)) return min
  return Math.max(min, Math.min(max, value))
}

function emptyReasoningStats(): ReasoningStats {
  return {
    thoughts: 0,
    tools: 0,
    knowledgeHits: 0,
    finalAnswers: 0,
  }
}

function mergeReasoningStats(a: ReasoningStats, b: ReasoningStats): ReasoningStats {
  return {
    thoughts: a.thoughts + b.thoughts,
    tools: a.tools + b.tools,
    knowledgeHits: a.knowledgeHits + b.knowledgeHits,
    finalAnswers: a.finalAnswers + b.finalAnswers,
  }
}

function getReasoningStats(spans: Span[]): ReasoningStats {
  return spans.reduce((acc, span) => {
    const output = (span.output_data || {}) as Record<string, unknown>
    const metadata = (span.metadata || {}) as Record<string, unknown>

    if (span.span_type === 'react_iter') {
      acc.thoughts += 1
      if (output.final_answer) {
        acc.finalAnswers += 1
      }
    }
    if (span.span_type === 'llm_call') {
      acc.thoughts += 1
    }
    if (span.span_type === 'tool_call') {
      acc.tools += 1
      const ragStats = metadata.rag_stats as Record<string, unknown> | undefined
      const hitCount = ragStats?.hit_count
      if (typeof hitCount === 'number') {
        acc.knowledgeHits += hitCount
      }
    }
    if (output.final_answer || output.answer || output.processing_result) {
      acc.finalAnswers += 1
    }

    if (span.children?.length) {
      return mergeReasoningStats(acc, getReasoningStats(span.children))
    }
    return acc
  }, emptyReasoningStats())
}

interface ChildSummary {
  text: string | null
  detailable: boolean
}

interface InsightItem {
  key: string
  label: string
  value: string
  tone?: 'primary' | 'success' | 'warning' | 'muted'
  compact?: boolean
}

function InsightPreview({ item }: { item: InsightItem }) {
  return (
    <div className={`rounded border px-2 py-1.5 ${getInsightTone(item.tone)}`}>
      <div className="mb-0.5 text-[9px] font-medium uppercase tracking-wide opacity-75">
        {item.label}
      </div>
      <p className="line-clamp-2 text-[10px] leading-relaxed">
        {item.value}
      </p>
    </div>
  )
}

function InsightBlock({ item }: { item: InsightItem }) {
  const isLong = item.value.length > 180
  const [expanded, setExpanded] = useState(!isLong)
  const display = expanded ? item.value : `${item.value.slice(0, 180)}... (+${item.value.length - 180} 字)`

  return (
    <section className={`rounded border px-2.5 py-2 ${getInsightTone(item.tone)}`}>
      <div className="mb-1 flex items-center gap-2">
        {isLong && (
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="text-current opacity-70 hover:opacity-100"
          >
            {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          </button>
        )}
        <span className="text-[10px] font-semibold uppercase tracking-wide opacity-80">
          {item.label}
        </span>
      </div>
      <p className="whitespace-pre-wrap break-words text-[11px] leading-relaxed">
        {display}
      </p>
    </section>
  )
}

function getInsightTone(tone: InsightItem['tone'] = 'muted'): string {
  if (tone === 'primary') return 'border-primary/30 bg-primary/5 text-primary'
  if (tone === 'success') return 'border-success/30 bg-success/5 text-success'
  if (tone === 'warning') return 'border-warning/30 bg-warning/5 text-warning'
  return 'border-border/70 bg-card/40 text-foreground/85'
}

function extractSpanHighlights(span: Span): InsightItem[] {
  const input = (span.input_data || {}) as Record<string, unknown>
  const out = (span.output_data || {}) as Record<string, unknown>
  const meta = (span.metadata || {}) as Record<string, unknown>
  const items: InsightItem[] = []

  if (span.span_type === 'react_iter') {
    addInsight(items, 'thought', 'LLM 思考', pickString(out.thought, meta.thought), 'primary')
    addInsight(items, 'action', '下一步动作', formatAction(out.action), 'warning')
    addInsight(items, 'observation', '观察结果', pickString(out.observation), 'success')
    addInsight(items, 'raw_response', '原始回复', pickString(out.raw_response), 'muted')
    addInsight(items, 'final_answer', '最终答案', pickString(out.final_answer), 'success')
    return items
  }

  if (span.span_type === 'llm_call') {
    addInsight(items, 'content', 'LLM 回复', pickString(out.content, out.response, out.answer), 'primary')
    addInsight(items, 'finish_reason', '结束原因', pickString(out.finish_reason), 'muted')
    addInsight(items, 'token_usage', 'Token 用量', formatTokenUsage(meta.token_usage), 'success')
    addInsight(items, 'messages_preview', '上下文摘要', formatMessagesPreview(input.messages_preview), 'muted')
    return items
  }

  if (span.span_type === 'tool_call') {
    addInsight(items, 'tool', '工具', pickString(input.tool, meta.tool_name, span.name), 'primary')
    addInsight(items, 'params', '调用参数', formatJson(input.params ?? input.tool_args ?? meta.tool_args), 'muted')
    addInsight(items, 'observation', '工具返回', pickString(out.observation, out.result, out.content), 'success')
    return items
  }

  addInsight(items, 'output', '输出', formatJson(out), 'muted')
  return items
}

function addInsight(
  items: InsightItem[],
  key: string,
  label: string,
  value: string | null,
  tone?: InsightItem['tone'],
) {
  if (!value || value.trim().length === 0 || value === '{}') return
  items.push({ key, label, value, tone })
}

function pickString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === 'string' && value.trim().length > 0) return value.trim()
    if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  }
  return null
}

function formatAction(value: unknown): string | null {
  if (!value) return null
  if (typeof value === 'string') return value
  if (typeof value !== 'object') return String(value)
  const action = value as Record<string, unknown>
  const tool = pickString(action.tool, action.name)
  const params = formatJson(action.params)
  if (!tool && !params) return formatJson(value)
  return [tool ? `工具：${tool}` : null, params ? `参数：${params}` : null].filter(Boolean).join('\n')
}

function formatTokenUsage(value: unknown): string | null {
  if (!value || typeof value !== 'object') return null
  const usage = value as Record<string, unknown>
  const total = usage.total_tokens ?? '-'
  const prompt = usage.prompt_tokens ?? '-'
  const completion = usage.completion_tokens ?? '-'
  return `总计 ${total}，Prompt ${prompt}，Completion ${completion}`
}

function formatMessagesPreview(value: unknown): string | null {
  if (!Array.isArray(value) || value.length === 0) return null
  return value
    .map((message, index) => {
      if (!message || typeof message !== 'object') return null
      const data = message as Record<string, unknown>
      const role = pickString(data.role) || 'unknown'
      const content = pickString(data.content) || ''
      return `#${index + 1} ${role}\n${content}`
    })
    .filter(Boolean)
    .join('\n\n')
}

function formatJson(value: unknown): string | null {
  if (value == null) return null
  if (typeof value === 'string') return value.trim() || null
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function summarizeChildOutput(span: Span): ChildSummary {
  const out = (span.output_data || {}) as Record<string, unknown>
  const meta = (span.metadata || {}) as Record<string, unknown>

  if (span.span_type === 'tool_call') {
    const ragStats = meta.rag_stats as Record<string, unknown> | undefined
    if (ragStats) {
      const hit = ragStats.hit_count as number | undefined
      const top = ragStats.top_score as number | undefined
      const query = ragStats.query as string | undefined
      const queryText = query ? `查询"${truncate(query, 30)}" ` : ''
      return {
        text: `${queryText}命中 ${hit ?? 0} 条知识片段，最高相似度 ${typeof top === 'number' ? top.toFixed(3) : '-'}`,
        detailable: true,
      }
    }
    const toolName = meta.tool_name as string | undefined
    return {
      text: typeof toolName === 'string' ? `调用工具：${toolName}` : '工具调用完成',
      detailable: !!out.result || !!out.content,
    }
  }

  if (span.span_type === 'llm_call') {
    const content = extractMarkdownFromSpan(span)
    if (content) {
      return {
        text: content.slice(0, 200) + (content.length > 200 ? '...' : ''),
        detailable: true,
      }
    }
    const tokenUsage = meta.token_usage as Record<string, unknown> | undefined
    if (tokenUsage) {
      const total = tokenUsage.total_tokens
      return {
        text: `Token 用量：${typeof total === 'number' ? total : '-'}（含 prompt ${tokenUsage.prompt_tokens ?? '-'} + completion ${tokenUsage.completion_tokens ?? '-'}）`,
        detailable: false,
      }
    }
    return { text: 'LLM 推理完成', detailable: false }
  }

  if (span.span_type === 'react_iter') {
    const thought = (out.thought || meta.thought) as string | undefined
    const action = formatAction(out.action)
    const observation = out.observation as string | undefined
    const iter = meta.iteration as number | undefined
    const parts: string[] = []
    if (iter != null) parts.push(`第 ${iter + 1} 轮`)
    if (thought) parts.push(`思考：${truncate(thought, 80)}`)
    if (action) parts.push(`行动：${action}`)
    if (observation) parts.push(`观察：${truncate(observation, 60)}`)
    return {
      text: parts.join(' · ') || 'ReAct 推理迭代',
      detailable: !!(thought || action || observation),
    }
  }

  if (span.span_type === 'memory_call') {
    const keys = out.context_keys as unknown[] | undefined
    return {
      text: `加载用户上下文 ${Array.isArray(keys) ? keys.length : 0} 个字段`,
      detailable: false,
    }
  }

  if (span.span_type === 'human_decision') {
    const decision = out.decision as string | undefined
    const ai = out.ai_adopted as boolean | undefined
    return {
      text: `决策：${decision || '-'}${ai != null ? ` (AI 建议${ai ? '已采纳' : '未采纳'})` : ''}`,
      detailable: false,
    }
  }

  const fallback = out.content as string | undefined
    || out.result as string | undefined
    || out.answer as string | undefined
  return {
    text: typeof fallback === 'string' ? truncate(fallback, 100) : null,
    detailable: typeof fallback === 'string',
  }
}

function extractMarkdownFromSpan(span: Span): string | null {
  const out = (span.output_data || {}) as Record<string, unknown>
  const candidates = ['content', 'answer', 'final_answer', 'processing_result', 'reply']
  for (const key of candidates) {
    const val = out[key]
    if (typeof val === 'string' && val.trim().length > 0) {
      return val
    }
  }
  return null
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}...` : text
}
