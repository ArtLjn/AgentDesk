import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTickets, useCreateTicket } from '@/hooks/useApi'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from '@/components/ui/dialog'
import { StatusBadge, CategoryBadge, PriorityBadge } from '@/components/layout/StatusBadge'
import type { Ticket } from '@/types'
import {
  Bot, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Loader2, Plus, RefreshCw, Search, SendHorizontal, Sparkles,
} from 'lucide-react'

const PAGE_SIZE_OPTIONS = [10, 20, 50]

const EXAMPLE_PROMPTS = [
  '今天上午 10:15 开始后台一直 504，部分业务人员无法登录，请尽快恢复，联系 ops@example.com',
  '上个月账单多扣了 200 元，已经核对订单记录，请帮我退款，手机号 13800000000',
  '我找不到导出本月工单报表的入口，请告知在哪里操作',
]

interface AgentTicketComposerProps {
  compact?: boolean
  onCreated?: () => void
}

function AgentTicketComposer({ compact = false, onCreated }: AgentTicketComposerProps) {
  const [userId, setUserId] = useState('U001')
  const [content, setContent] = useState('')
  const createMutation = useCreateTicket()

  const canSubmit = content.trim().length >= 8 && !createMutation.isPending

  const handleSubmit = async () => {
    if (!canSubmit) return
    await createMutation.mutateAsync({
      content: content.trim(),
      user_id: userId.trim() || undefined,
    })
    setContent('')
    onCreated?.()
  }

  const loadExample = () => {
    const next = EXAMPLE_PROMPTS[Math.floor(Math.random() * EXAMPLE_PROMPTS.length)]
    setContent(next)
  }

  return (
    <div className={compact ? 'space-y-4' : 'rounded-xl border border-border bg-card p-4 shadow-sm'}>
      {!compact && (
        <div className="mb-4 flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/15 text-primary">
              <Bot className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold">AI 创建工单</h3>
                <Badge variant="outline" className="border-primary/30 bg-primary/10 text-[10px] text-primary">
                  Agent 理解
                </Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                直接描述问题，后端 Agent 会自动提取类型、优先级、影响范围和联系方式。
              </p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={loadExample} type="button">
            <Sparkles className="h-3.5 w-3.5" />
            示例
          </Button>
        </div>
      )}

      <div className="grid gap-3 lg:grid-cols-[140px_1fr_auto]">
        <Input
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="用户 ID"
          className="h-9"
        />
        <Textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="例如：今天上午 10:15 开始后台一直 504，部分业务人员无法登录，请尽快恢复，联系 ops@example.com"
          rows={compact ? 5 : 2}
          className="min-h-[72px] resize-none"
        />
        <div className="flex items-end gap-2 lg:flex-col lg:justify-end">
          {compact && (
            <Button variant="outline" onClick={loadExample} type="button">
              <Sparkles className="h-3.5 w-3.5" />
              填入示例
            </Button>
          )}
          <Button onClick={handleSubmit} disabled={!canSubmit} className={compact ? 'min-w-28' : 'min-w-24'}>
            {createMutation.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <SendHorizontal className="h-3.5 w-3.5" />
            )}
            {createMutation.isPending ? '创建中' : '创建'}
          </Button>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
        <span>Agent 将自动生成：</span>
        <Badge variant="secondary" className="text-[10px]">问题标题</Badge>
        <Badge variant="secondary" className="text-[10px]">分类</Badge>
        <Badge variant="secondary" className="text-[10px]">优先级</Badge>
        <Badge variant="secondary" className="text-[10px]">影响范围</Badge>
      </div>
    </div>
  )
}

export function Tickets() {
  const navigate = useNavigate()
  const [status, setStatus] = useState<string>('')
  const [category, setCategory] = useState<string>('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [dialogOpen, setDialogOpen] = useState(false)

  const params: Record<string, string> = {}
  if (status) params.status = status
  if (category) params.category = category

  const { data: tickets = [], isLoading, refetch } = useTickets(params)

  const filtered = useMemo(() => {
    if (!search) return tickets
    const s = search.toLowerCase()
    return tickets.filter((t: Ticket) =>
      t.content?.toLowerCase().includes(s) ||
      t.ticket_id?.toLowerCase().includes(s),
    )
  }, [tickets, search])

  const total = filtered.length
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const currentPage = Math.min(page, totalPages)
  const startIdx = (currentPage - 1) * pageSize
  const endIdx = Math.min(startIdx + pageSize, total)
  const pageItems = filtered.slice(startIdx, endIdx)

  const pageNumbers = useMemo(() => {
    const max = 5
    if (totalPages <= max) return Array.from({ length: totalPages }, (_, i) => i + 1)
    const start = Math.max(1, Math.min(currentPage - 2, totalPages - max + 1))
    return Array.from({ length: max }, (_, i) => start + i)
  }, [currentPage, totalPages])

  const handleCreatedFromDialog = () => {
    setDialogOpen(false)
    refetch()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">工单管理</h2>
          <p className="mt-1 text-sm text-muted-foreground">管理和追踪所有工单</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger render={<Button size="sm" />}>
            <Plus className="h-4 w-4" />
            提交工单
          </DialogTrigger>
          <DialogContent className="border-border bg-card sm:max-w-[680px]">
            <DialogHeader>
              <div className="flex items-start gap-3 pr-8">
                <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/15 text-primary">
                  <Bot className="h-5 w-5" />
                </div>
                <div className="space-y-1">
                  <DialogTitle>AI 提交工单</DialogTitle>
                  <DialogDescription>
                    不需要填写传统表单，直接说清楚问题即可。
                  </DialogDescription>
                </div>
              </div>
            </DialogHeader>
            <AgentTicketComposer compact onCreated={handleCreatedFromDialog} />
            <DialogFooter className="border-t border-border pt-4 text-xs text-muted-foreground">
              后端 Agent 会先理解意图，再创建并分派工单。
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <AgentTicketComposer onCreated={() => refetch()} />

      <Card className="border-border bg-card">
        <CardContent className="p-3">
          <div className="flex items-center gap-3">
            <div className="relative max-w-xs flex-1">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="搜索工单..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value)
                  setPage(1)
                }}
                className="h-8 pl-8 text-sm"
              />
            </div>
            <Select
              value={status}
              onValueChange={(v) => {
                setStatus(v === 'all' ? '' : (v ?? ''))
                setPage(1)
              }}
            >
              <SelectTrigger className="h-8 w-32 text-sm">
                <SelectValue placeholder="全部状态" />
              </SelectTrigger>
              <SelectContent className="border-border bg-popover">
                <SelectItem value="all">全部状态</SelectItem>
                <SelectItem value="received">已接收</SelectItem>
                <SelectItem value="classifying">分类中</SelectItem>
                <SelectItem value="processing">处理中</SelectItem>
                <SelectItem value="reviewing">审核中</SelectItem>
                <SelectItem value="completed">已完成</SelectItem>
                <SelectItem value="failed">失败</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={category}
              onValueChange={(v) => {
                setCategory(v === 'all' ? '' : (v ?? ''))
                setPage(1)
              }}
            >
              <SelectTrigger className="h-8 w-32 text-sm">
                <SelectValue placeholder="全部分类" />
              </SelectTrigger>
              <SelectContent className="border-border bg-popover">
                <SelectItem value="all">全部分类</SelectItem>
                <SelectItem value="technical">技术支持</SelectItem>
                <SelectItem value="billing">账务问题</SelectItem>
                <SelectItem value="complaint">投诉建议</SelectItem>
                <SelectItem value="inquiry">咨询问询</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RefreshCw className="h-3.5 w-3.5" />
              刷新
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="overflow-hidden border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow className="border-border hover:bg-transparent">
              <TableHead className="h-11 w-[160px] px-4 text-xs font-medium text-muted-foreground">工单 ID</TableHead>
              <TableHead className="h-11 px-4 text-xs font-medium text-muted-foreground">内容</TableHead>
              <TableHead className="h-11 w-[110px] px-4 text-xs font-medium text-muted-foreground">分类</TableHead>
              <TableHead className="h-11 w-[90px] px-4 text-xs font-medium text-muted-foreground">优先级</TableHead>
              <TableHead className="h-11 w-[120px] px-4 text-xs font-medium text-muted-foreground">状态</TableHead>
              <TableHead className="h-11 w-[80px] px-4 text-right text-xs font-medium text-muted-foreground">评分</TableHead>
              <TableHead className="h-11 w-[150px] px-4 text-right text-xs font-medium text-muted-foreground">创建时间</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: pageSize }).map((_, i) => (
                <TableRow key={i} className="border-border">
                  {Array.from({ length: 7 }).map((_, j) => (
                    <TableCell key={j} className="px-4 py-3">
                      <div className="h-4 w-24 animate-pulse rounded bg-muted" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : pageItems.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="py-16 text-center text-sm text-muted-foreground">
                  暂无工单数据
                </TableCell>
              </TableRow>
            ) : (
              pageItems.map((ticket: Ticket) => (
                <TableRow
                  key={ticket.ticket_id}
                  className="cursor-pointer border-border transition-colors hover:bg-muted/40"
                  onClick={() => navigate(`/tickets/${ticket.ticket_id}`)}
                >
                  <TableCell className="px-4 py-3 font-mono text-[12px] text-primary">{ticket.ticket_id?.slice(0, 16)}</TableCell>
                  <TableCell className="max-w-[420px] truncate px-4 py-3 text-[13px]">{ticket.content}</TableCell>
                  <TableCell className="px-4 py-3">{ticket.category ? <CategoryBadge category={ticket.category} /> : '-'}</TableCell>
                  <TableCell className="px-4 py-3">{ticket.priority ? <PriorityBadge priority={ticket.priority} /> : '-'}</TableCell>
                  <TableCell className="px-4 py-3"><StatusBadge status={ticket.status} /></TableCell>
                  <TableCell className="px-4 py-3 text-right font-mono text-[12px] tabular-nums">
                    {ticket.review_score != null ? ticket.review_score.toFixed(2) : '-'}
                  </TableCell>
                  <TableCell className="px-4 py-3 text-right text-[12px] tabular-nums text-muted-foreground">
                    {ticket.created_at ? new Date(ticket.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-'}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>

        <div className="flex items-center justify-between gap-4 border-t border-border bg-muted/20 px-4 py-3">
          <div className="text-xs tabular-nums text-muted-foreground">
            {total === 0 ? '共 0 条' : `第 ${startIdx + 1}-${endIdx} 条，共 ${total} 条`}
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setPage(1)}
              disabled={currentPage <= 1}
              title="第一页"
            >
              <ChevronsLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={currentPage <= 1}
              title="上一页"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            {pageNumbers.map(p => (
              <Button
                key={p}
                variant={p === currentPage ? 'default' : 'ghost'}
                size="icon"
                className="h-8 w-8 text-xs tabular-nums"
                onClick={() => setPage(p)}
              >
                {p}
              </Button>
            ))}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage >= totalPages}
              title="下一页"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setPage(totalPages)}
              disabled={currentPage >= totalPages}
              title="最后一页"
            >
              <ChevronsRight className="h-4 w-4" />
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">每页</span>
            <Select
              value={String(pageSize)}
              onValueChange={(v) => {
                setPageSize(Number(v))
                setPage(1)
              }}
            >
              <SelectTrigger className="h-8 w-[70px] text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="border-border bg-popover">
                {PAGE_SIZE_OPTIONS.map(n => (
                  <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <span className="text-xs text-muted-foreground">条</span>
          </div>
        </div>
      </Card>
    </div>
  )
}
