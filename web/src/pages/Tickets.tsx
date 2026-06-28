import { useMemo, useState, type ReactNode } from 'react'
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
  AlertTriangle, CheckCircle2, Clock3, FileText, LifeBuoy, Paperclip, Plus, RefreshCw, Search, Sparkles,
  ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight,
} from 'lucide-react'

const PAGE_SIZE_OPTIONS = [10, 20, 50]

const ticketTypeOptions = [
  { value: 'technical', label: '技术支持', hint: '系统故障、接口异常、权限问题' },
  { value: 'billing', label: '账务问题', hint: '扣费、退款、账单核对' },
  { value: 'complaint', label: '投诉建议', hint: '服务体验、处理不满意' },
  { value: 'inquiry', label: '咨询问询', hint: '功能入口、操作方式、规则咨询' },
]

const priorityOptions = [
  { value: 'P0', label: 'P0 紧急', hint: '核心业务不可用' },
  { value: 'P1', label: 'P1 高', hint: '影响多人或关键流程' },
  { value: 'P2', label: 'P2 普通', hint: '常规问题处理' },
  { value: 'P3', label: 'P3 低', hint: '咨询、建议或低影响' },
]

const impactOptions = [
  '仅本人受影响',
  '部分用户受影响',
  '全部用户受影响',
  '核心业务不可用',
]

const sampleTickets = [
  {
    type: 'technical',
    priority: 'P0',
    impact: '核心业务不可用',
    title: '数据库连接超时导致系统无法访问',
    detail: '从今天上午 10:15 开始，后台登录后页面一直加载，接口偶发返回 504，业务人员无法查看客户数据。',
    expectation: '请优先恢复系统访问，并说明是否需要回滚最近发布。',
    contact: '张三 13800000000',
  },
  {
    type: 'billing',
    priority: 'P1',
    impact: '仅本人受影响',
    title: '账单金额异常，多扣 200 元',
    detail: '上个月套餐应为 399 元，实际账单显示扣费 599 元，已经核对过订单记录。',
    expectation: '请协助核对账单并发起退款。',
    contact: 'finance@example.com',
  },
  {
    type: 'inquiry',
    priority: 'P3',
    impact: '仅本人受影响',
    title: '找不到导出 Excel 报表入口',
    detail: '需要导出本月工单处理报表，但在工单列表和详情页都没有看到导出按钮。',
    expectation: '请告知具体入口或需要开通的权限。',
    contact: 'U001',
  },
]

function optionLabel(options: Array<{ value: string; label: string }>, value: string) {
  return options.find(option => option.value === value)?.label ?? value
}

function FormField({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: ReactNode
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
      {hint && <span className="block text-[11px] leading-4 text-muted-foreground/75">{hint}</span>}
    </label>
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
  const [newUserId, setNewUserId] = useState('U001')
  const [newType, setNewType] = useState('technical')
  const [newPriority, setNewPriority] = useState('P2')
  const [newImpact, setNewImpact] = useState('仅本人受影响')
  const [newTitle, setNewTitle] = useState('')
  const [newDetail, setNewDetail] = useState('')
  const [newExpectation, setNewExpectation] = useState('')
  const [newContact, setNewContact] = useState('')
  const [newOccurredAt, setNewOccurredAt] = useState('')

  const params: Record<string, string> = {}
  if (status) params.status = status
  if (category) params.category = category

  const { data: tickets = [], isLoading, refetch } = useTickets(params)
  const createMutation = useCreateTicket()

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

  const resetCreateForm = () => {
    setNewType('technical')
    setNewPriority('P2')
    setNewImpact('仅本人受影响')
    setNewTitle('')
    setNewDetail('')
    setNewExpectation('')
    setNewContact('')
    setNewOccurredAt('')
  }

  const buildTicketContent = () => {
    const rows = [
      `【问题类型】${optionLabel(ticketTypeOptions, newType)}`,
      `【紧急程度】${optionLabel(priorityOptions, newPriority)}`,
      `【影响范围】${newImpact}`,
      `【问题标题】${newTitle.trim()}`,
      `【问题描述】${newDetail.trim()}`,
      newExpectation.trim() ? `【期望处理】${newExpectation.trim()}` : '',
      newOccurredAt.trim() ? `【发生时间】${newOccurredAt.trim()}` : '',
      newContact.trim() ? `【联系方式】${newContact.trim()}` : '',
    ]

    return rows.filter(Boolean).join('\n')
  }

  const handleCreate = async () => {
    if (!newTitle.trim() || !newDetail.trim()) return
    await createMutation.mutateAsync({ content: buildTicketContent(), user_id: newUserId || undefined })
    resetCreateForm()
    setDialogOpen(false)
    refetch()
  }

  const loadSample = () => {
    const sample = sampleTickets[Math.floor(Math.random() * sampleTickets.length)]
    setNewType(sample.type)
    setNewPriority(sample.priority)
    setNewImpact(sample.impact)
    setNewTitle(sample.title)
    setNewDetail(sample.detail)
    setNewExpectation(sample.expectation)
    setNewContact(sample.contact)
  }

  const canCreate = newTitle.trim().length > 0 && newDetail.trim().length > 0 && !createMutation.isPending
  const previewContent = buildTicketContent()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">工单管理</h2>
          <p className="text-sm text-muted-foreground mt-1">管理和追踪所有工单</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger
            render={<Button size="sm" />}
          >
            <Plus className="w-4 h-4 mr-1.5" />
            提交工单
          </DialogTrigger>
          <DialogContent className="max-h-[90vh] overflow-y-auto border-border bg-card p-0 sm:max-w-[760px]">
            <DialogHeader className="border-b border-border bg-muted/20 px-6 py-5">
              <div className="flex items-start gap-3 pr-8">
                <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/15 text-primary">
                  <LifeBuoy className="h-5 w-5" />
                </div>
                <div className="space-y-1">
                  <DialogTitle className="text-lg">提交新工单</DialogTitle>
                  <DialogDescription>
                    补充关键信息后，系统会自动分类、判断优先级并进入处理流程。
                  </DialogDescription>
                </div>
              </div>
            </DialogHeader>
            <div className="grid gap-5 px-6 py-5 lg:grid-cols-[1fr_220px]">
              <div className="space-y-5">
                <section className="space-y-3">
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-primary" />
                    <h3 className="text-sm font-semibold">基础信息</h3>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <FormField label="用户 ID" hint="可留空，留空时按匿名工单处理">
                      <Input value={newUserId} onChange={(e) => setNewUserId(e.target.value)} placeholder="例如 U001" />
                    </FormField>
                    <FormField label="问题类型">
                      <Select value={newType} onValueChange={(v) => setNewType(v ?? 'technical')}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-popover border-border">
                          {ticketTypeOptions.map(option => (
                            <SelectItem key={option.value} value={option.value}>
                              <span className="flex flex-col gap-0.5">
                                <span>{option.label}</span>
                                <span className="text-[11px] text-muted-foreground">{option.hint}</span>
                              </span>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FormField>
                    <FormField label="紧急程度">
                      <div className="grid grid-cols-2 gap-2">
                        {priorityOptions.map(option => (
                          <button
                            key={option.value}
                            type="button"
                            onClick={() => setNewPriority(option.value)}
                            className={`rounded-lg border px-3 py-2 text-left transition-colors ${
                              newPriority === option.value
                                ? 'border-primary bg-primary/15 text-primary'
                                : 'border-border bg-muted/20 text-foreground hover:bg-muted/40'
                            }`}
                          >
                            <span className="block text-xs font-semibold">{option.label}</span>
                            <span className="mt-0.5 block text-[11px] leading-4 text-muted-foreground">{option.hint}</span>
                          </button>
                        ))}
                      </div>
                    </FormField>
                    <FormField label="影响范围">
                      <Select value={newImpact} onValueChange={(v) => setNewImpact(v ?? '仅本人受影响')}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-popover border-border">
                          {impactOptions.map(option => (
                            <SelectItem key={option} value={option}>{option}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FormField>
                  </div>
                </section>

                <section className="space-y-3">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-warning" />
                    <h3 className="text-sm font-semibold">问题描述</h3>
                    <Badge variant="outline" className="border-primary/30 bg-primary/10 text-[10px] text-primary">
                      必填
                    </Badge>
                  </div>
                  <FormField label="问题标题">
                    <Input
                      value={newTitle}
                      onChange={(e) => setNewTitle(e.target.value)}
                      placeholder="用一句话说明问题，例如：API 返回 403 导致数据同步失败"
                    />
                  </FormField>
                  <FormField label="详细描述" hint="建议写清楚现象、复现步骤、报错信息和已尝试的处理方式">
                    <Textarea
                      value={newDetail}
                      onChange={(e) => setNewDetail(e.target.value)}
                      placeholder="请描述你遇到的问题..."
                      rows={5}
                      className="min-h-[120px]"
                    />
                  </FormField>
                  <FormField label="期望处理结果">
                    <Input
                      value={newExpectation}
                      onChange={(e) => setNewExpectation(e.target.value)}
                      placeholder="例如：恢复访问、核对账单、告知操作入口"
                    />
                  </FormField>
                </section>

                <section className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Clock3 className="h-4 w-4 text-muted-foreground" />
                    <h3 className="text-sm font-semibold">辅助信息</h3>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <FormField label="联系方式">
                      <Input
                        value={newContact}
                        onChange={(e) => setNewContact(e.target.value)}
                        placeholder="手机号、邮箱或企业微信"
                      />
                    </FormField>
                    <FormField label="发生时间">
                      <Input
                        value={newOccurredAt}
                        onChange={(e) => setNewOccurredAt(e.target.value)}
                        placeholder="例如 今天 10:15"
                      />
                    </FormField>
                  </div>
                  <div className="rounded-lg border border-dashed border-border bg-muted/20 p-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-background text-muted-foreground">
                        <Paperclip className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="text-sm font-medium">附件材料</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">当前接口暂未接入附件上传，可先在描述中补充截图链接或日志片段。</p>
                      </div>
                    </div>
                  </div>
                </section>
              </div>

              <aside className="space-y-3">
                <div className="rounded-lg border border-border bg-muted/20 p-4">
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    <Sparkles className="h-4 w-4 text-primary" />
                    提交后流程
                  </div>
                  <div className="mt-4 space-y-3">
                    {['接收工单', 'Agent 自动分类', '生成处理方案', '必要时人工审核'].map((step, index) => (
                      <div key={step} className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/15 text-[10px] font-semibold text-primary">
                          {index + 1}
                        </span>
                        <span>{step}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="rounded-lg border border-border bg-background/60 p-4">
                  <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
                    <CheckCircle2 className="h-4 w-4 text-success" />
                    提交摘要
                  </div>
                  <div className="space-y-2 text-xs text-muted-foreground">
                    <div className="flex justify-between gap-3">
                      <span>类型</span>
                      <span className="text-foreground">{optionLabel(ticketTypeOptions, newType)}</span>
                    </div>
                    <div className="flex justify-between gap-3">
                      <span>优先级</span>
                      <span className="text-foreground">{optionLabel(priorityOptions, newPriority)}</span>
                    </div>
                    <div className="flex justify-between gap-3">
                      <span>影响</span>
                      <span className="text-right text-foreground">{newImpact}</span>
                    </div>
                  </div>
                  <div className="mt-3 max-h-32 overflow-hidden rounded-md border border-border bg-muted/20 p-3 text-[11px] leading-5 text-muted-foreground">
                    {previewContent || '填写标题和描述后，这里会预览提交给处理 Agent 的结构化内容。'}
                  </div>
                </div>
              </aside>
            </div>
            <DialogFooter className="mx-0 mb-0 rounded-none border-border bg-muted/20 px-6 py-4">
              <Button variant="outline" onClick={loadSample} type="button">
                填入示例
              </Button>
              <Button onClick={handleCreate} disabled={!canCreate}>
                {createMutation.isPending ? '提交中...' : '提交工单'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* 过滤栏 */}
      <Card className="bg-card border-border">
        <CardContent className="p-3">
          <div className="flex gap-3 items-center">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-muted-foreground" />
              <Input
                placeholder="搜索工单..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value)
                  setPage(1)
                }}
                className="pl-8 h-8 text-sm"
              />
            </div>
            <Select
              value={status}
              onValueChange={(v) => {
                setStatus(v === 'all' ? '' : (v ?? ''))
                setPage(1)
              }}
            >
              <SelectTrigger className="w-32 h-8 text-sm">
                <SelectValue placeholder="全部状态" />
              </SelectTrigger>
              <SelectContent className="bg-popover border-border">
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
              <SelectTrigger className="w-32 h-8 text-sm">
                <SelectValue placeholder="全部分类" />
              </SelectTrigger>
              <SelectContent className="bg-popover border-border">
                <SelectItem value="all">全部分类</SelectItem>
                <SelectItem value="technical">技术支持</SelectItem>
                <SelectItem value="billing">账务问题</SelectItem>
                <SelectItem value="complaint">投诉建议</SelectItem>
                <SelectItem value="inquiry">咨询问询</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RefreshCw className="w-3.5 h-3.5 mr-1" />
              刷新
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 工单表格 */}
      <Card className="bg-card border-border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-border hover:bg-transparent">
              <TableHead className="text-muted-foreground text-xs font-medium h-11 px-4 w-[160px]">工单 ID</TableHead>
              <TableHead className="text-muted-foreground text-xs font-medium h-11 px-4">内容</TableHead>
              <TableHead className="text-muted-foreground text-xs font-medium h-11 px-4 w-[110px]">分类</TableHead>
              <TableHead className="text-muted-foreground text-xs font-medium h-11 px-4 w-[90px]">优先级</TableHead>
              <TableHead className="text-muted-foreground text-xs font-medium h-11 px-4 w-[120px]">状态</TableHead>
              <TableHead className="text-muted-foreground text-xs font-medium h-11 px-4 text-right w-[80px]">评分</TableHead>
              <TableHead className="text-muted-foreground text-xs font-medium h-11 px-4 text-right w-[150px]">创建时间</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: pageSize }).map((_, i) => (
                <TableRow key={i} className="border-border">
                  {Array.from({ length: 7 }).map((_, j) => (
                    <TableCell key={j} className="py-3 px-4">
                      <div className="h-4 w-24 bg-muted rounded animate-pulse" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : pageItems.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-16 text-sm">
                  暂无工单数据
                </TableCell>
              </TableRow>
            ) : (
              pageItems.map((ticket: Ticket) => (
                <TableRow
                  key={ticket.ticket_id}
                  className="border-border cursor-pointer hover:bg-muted/40 transition-colors"
                  onClick={() => navigate(`/tickets/${ticket.ticket_id}`)}
                >
                  <TableCell className="font-mono text-[12px] text-primary py-3 px-4">{ticket.ticket_id?.slice(0, 16)}</TableCell>
                  <TableCell className="max-w-[420px] truncate text-[13px] py-3 px-4">{ticket.content}</TableCell>
                  <TableCell className="py-3 px-4">{ticket.category ? <CategoryBadge category={ticket.category} /> : '-'}</TableCell>
                  <TableCell className="py-3 px-4">{ticket.priority ? <PriorityBadge priority={ticket.priority} /> : '-'}</TableCell>
                  <TableCell className="py-3 px-4"><StatusBadge status={ticket.status} /></TableCell>
                  <TableCell className="font-mono text-[12px] py-3 px-4 text-right tabular-nums">
                    {ticket.review_score != null ? ticket.review_score.toFixed(2) : '-'}
                  </TableCell>
                  <TableCell className="text-[12px] text-muted-foreground py-3 px-4 text-right tabular-nums">
                    {ticket.created_at ? new Date(ticket.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-'}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>

        {/* 分页栏 */}
        <div className="flex items-center justify-between gap-4 px-4 py-3 border-t border-border bg-muted/20">
          <div className="text-xs text-muted-foreground tabular-nums">
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
              <SelectTrigger className="w-[70px] h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-popover border-border">
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
