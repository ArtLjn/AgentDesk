import { useState } from 'react'
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
import { Plus, Search, RefreshCw } from 'lucide-react'

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
  const [dialogOpen, setDialogOpen] = useState(false)
  const [newContent, setNewContent] = useState('')
  const [newUserId, setNewUserId] = useState('U001')

  const params: Record<string, string> = {}
  if (status) params.status = status
  if (category) params.category = category

  const { data: tickets = [], isLoading, refetch } = useTickets(params)
  const createMutation = useCreateTicket()

  const filtered = search
    ? tickets.filter((t: any) =>
        t.content?.toLowerCase().includes(search.toLowerCase()) ||
        t.ticket_id?.toLowerCase().includes(search.toLowerCase())
      )
    : tickets

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
      <Card className="bg-card border-border">
        <Table>
          <TableHeader>
            <TableRow className="border-border hover:bg-transparent">
              <TableHead className="text-muted-foreground text-xs">工单 ID</TableHead>
              <TableHead className="text-muted-foreground text-xs">内容</TableHead>
              <TableHead className="text-muted-foreground text-xs">分类</TableHead>
              <TableHead className="text-muted-foreground text-xs">优先级</TableHead>
              <TableHead className="text-muted-foreground text-xs">状态</TableHead>
              <TableHead className="text-muted-foreground text-xs">评分</TableHead>
              <TableHead className="text-muted-foreground text-xs">创建时间</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i} className="border-border">
                  {Array.from({ length: 7 }).map((_, j) => (
                    <TableCell key={j}>
                      <div className="h-4 w-20 bg-muted rounded animate-pulse" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-12">
                  暂无工单数据
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((ticket: any) => (
                <TableRow
                  key={ticket.ticket_id}
                  className="border-border cursor-pointer hover:bg-muted/50 transition-colors"
                  onClick={() => navigate(`/tickets/${ticket.ticket_id}`)}
                >
                  <TableCell className="font-mono text-xs text-primary">{ticket.ticket_id?.slice(0, 16)}</TableCell>
                  <TableCell className="max-w-[240px] truncate text-sm">{ticket.content}</TableCell>
                  <TableCell>{ticket.category ? <CategoryBadge category={ticket.category} /> : '-'}</TableCell>
                  <TableCell>{ticket.priority ? <PriorityBadge priority={ticket.priority} /> : '-'}</TableCell>
                  <TableCell><StatusBadge status={ticket.status} /></TableCell>
                  <TableCell className="font-mono text-xs">
                    {ticket.review_score != null ? ticket.review_score.toFixed(2) : '-'}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {ticket.created_at ? new Date(ticket.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-'}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  )
}
