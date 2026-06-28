import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTickets, useCreateTicket } from '@/hooks/useApi'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from '@/components/ui/dialog'
import { StatusBadge, CategoryBadge, PriorityBadge } from '@/components/layout/StatusBadge'
import {
  Plus, Search, RefreshCw,
  ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight,
} from 'lucide-react'

const PAGE_SIZE_OPTIONS = [10, 20, 50]

const sampleContents = [
  '系统突然崩溃，无法启动，报错代码 ERR-5001',
  '如何修改个人资料？找不到入口',
  '退款什么时候到账？已经申请3天了',
  '我要投诉你们的客服，态度太差了！',
  '数据库连接超时，整个系统无法访问，紧急！',
  '上个月的账单金额不对，多扣了200元',
  '怎么导出报表为Excel格式？',
  'API接口返回403错误，权限配置有问题',
]

export function Tickets() {
  const navigate = useNavigate()
  const [status, setStatus] = useState<string>('')
  const [category, setCategory] = useState<string>('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [newContent, setNewContent] = useState('')
  const [newUserId, setNewUserId] = useState('U001')

  const params: Record<string, string> = {}
  if (status) params.status = status
  if (category) params.category = category

  const { data: tickets = [], isLoading, refetch } = useTickets(params)
  const createMutation = useCreateTicket()

  const filtered = useMemo(() => {
    if (!search) return tickets
    const s = search.toLowerCase()
    return tickets.filter((t: any) =>
      t.content?.toLowerCase().includes(s) ||
      t.ticket_id?.toLowerCase().includes(s),
    )
  }, [tickets, search])

  // 过滤/搜索/页大小变化时，自动回到第一页
  useEffect(() => { setPage(1) }, [status, category, search, pageSize])

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

  const handleCreate = async () => {
    if (!newContent.trim()) return
    await createMutation.mutateAsync({ content: newContent, user_id: newUserId || undefined })
    setNewContent('')
    setDialogOpen(false)
    refetch()
  }

  const loadSample = () => {
    setNewContent(sampleContents[Math.floor(Math.random() * sampleContents.length)])
  }

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
          <DialogContent className="bg-card border-border">
            <DialogHeader>
              <DialogTitle>提交新工单</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-2">
              <div>
                <label className="text-xs text-muted-foreground">用户 ID</label>
                <Input value={newUserId} onChange={(e) => setNewUserId(e.target.value)} className="mt-1" />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">工单内容</label>
                <Textarea
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                  placeholder="描述你遇到的问题..."
                  rows={4}
                  className="mt-1"
                />
              </div>
              <div className="flex gap-2">
                <Button onClick={handleCreate} disabled={!newContent.trim() || createMutation.isPending}>
                  提交
                </Button>
                <Button variant="outline" onClick={loadSample}>
                  填入示例
                </Button>
              </div>
            </div>
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
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8 h-8 text-sm"
              />
            </div>
            <Select value={status} onValueChange={(v) => setStatus(v === 'all' ? '' : (v ?? ''))}>
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
            <Select value={category} onValueChange={(v) => setCategory(v === 'all' ? '' : (v ?? ''))}>
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
              pageItems.map((ticket: any) => (
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
            <Select value={String(pageSize)} onValueChange={(v) => setPageSize(Number(v))}>
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
