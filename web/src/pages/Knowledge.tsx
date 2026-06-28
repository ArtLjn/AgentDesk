import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useKnowledge, useUploadKnowledge } from '@/hooks/useApi'
import { ApiError } from '@/lib/api'
import { filterKnowledgeDocuments } from '@/lib/knowledgeReference'
import type { KnowledgeDocument } from '@/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import { BookOpen, Upload, CheckCircle2, AlertCircle, FileText, Layers, Search, RefreshCw } from 'lucide-react'

const sampleDocs = [
  {
    title: '系统崩溃排查手册',
    category: 'technical',
    content: '系统崩溃常见原因：1. 内存不足 2. 数据库连接池耗尽 3. 磁盘空间满。处理时先查看服务端日志，再检查资源占用和依赖服务状态。',
  },
  {
    title: '退款流程说明',
    category: 'billing',
    content: '退款流程：1. 用户提交退款申请 2. 客服审核订单状态 3. 财务确认退款金额 4. 3-5 个工作日到账。',
  },
  {
    title: 'VIP 用户服务协议',
    category: 'complaint',
    content: 'VIP 用户享有优先处理权。投诉工单应在 2 小时内响应，处理结果需要记录回访状态和满意度。',
  },
]

export function Knowledge() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [category, setCategory] = useState('technical')
  const [selectedId, setSelectedId] = useState('')
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')
  const query = searchParams.get('q') || ''
  const activeCategory = searchParams.get('category') || ''

  const { data, isLoading, refetch } = useKnowledge({ limit: '200' })
  const uploadMutation = useUploadKnowledge()
  const documents = useMemo(() => data?.documents || [], [data?.documents])

  const filteredDocs = useMemo(() => {
    return filterKnowledgeDocuments(documents, {
      query,
      category: activeCategory,
    })
  }, [documents, query, activeCategory])

  const selectedDoc = filteredDocs.find((doc) => doc.id === selectedId)
    || filteredDocs[0]
    || null

  const categoryCount = useMemo(() => {
    return documents.reduce<Record<string, number>>((acc, doc) => {
      acc[doc.category || '未分类'] = (acc[doc.category || '未分类'] || 0) + 1
      return acc
    }, {})
  }, [documents])

  const handleUpload = async () => {
    if (!title.trim() || !content.trim()) return
    setSuccess(false)
    setError('')
    try {
      await uploadMutation.mutateAsync({ title, content, category })
      setSuccess(true)
      setTitle('')
      setContent('')
      setSelectedId('')
      setTimeout(() => setSuccess(false), 3000)
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail || err.message)
        return
      }
      setError('知识库上传失败，请稍后重试')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-primary" />
            知识库管理
          </h2>
          <p className="text-sm text-muted-foreground mt-1">查看、上传和核对 RAG 知识库文档</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
          刷新
        </Button>
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-4 space-y-4">
          <Card className="bg-card border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">上传新文档</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-xs text-muted-foreground">文档标题</label>
                <Input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="输入文档标题..."
                  className="mt-1"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">分类</label>
                <Input
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  placeholder="technical"
                  className="mt-1"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">内容</label>
                <Textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="输入文档内容..."
                  rows={8}
                  className="mt-1"
                />
              </div>
              <div className="flex items-center gap-2">
                <Button
                  onClick={handleUpload}
                  disabled={!title.trim() || !content.trim() || uploadMutation.isPending}
                >
                  <Upload className="w-4 h-4 mr-1.5" />
                  上传
                </Button>
                {success && (
                  <div className="flex items-center gap-1.5 text-success text-sm">
                    <CheckCircle2 className="w-4 h-4" />
                    上传成功
                  </div>
                )}
              </div>
              {error && (
                <div className="flex items-start gap-2 rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="bg-card border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">快速填充</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {sampleDocs.map((doc) => (
                <button
                  key={doc.title}
                  type="button"
                  onClick={() => {
                    setTitle(doc.title)
                    setContent(doc.content)
                    setCategory(doc.category)
                  }}
                  className="w-full rounded-md border border-border bg-background p-3 text-left transition-colors hover:border-primary/50"
                >
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium">{doc.title}</span>
                    <Badge variant="outline" className="border-0 bg-primary/15 text-[10px] text-primary">
                      {doc.category}
                    </Badge>
                  </div>
                  <p className="line-clamp-2 text-xs text-muted-foreground">{doc.content}</p>
                </button>
              ))}
            </CardContent>
          </Card>
        </div>

        <div className="col-span-4">
          <Card className="bg-card border-border">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="text-sm">现有文档</CardTitle>
                <Badge variant="outline" className="border-0 bg-secondary text-xs">
                  {documents.length} 篇
                </Badge>
              </div>
              <div className="relative mt-3">
                <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  value={query}
                  onChange={(e) => {
                    const value = e.target.value
                    setSelectedId('')
                    // 同步 URL（清空时移除 ?q=）
                    const next = new URLSearchParams(searchParams)
                    if (value) next.set('q', value)
                    else next.delete('q')
                    setSearchParams(next, { replace: true })
                  }}
                  placeholder="搜索标题、分类或内容..."
                  className="pl-8"
                />
              </div>
            </CardHeader>
            <CardContent>
              <CategoryChips
                categoryCount={categoryCount}
                activeCategory={activeCategory}
                onToggle={(c) => {
                  setSelectedId('')
                  const next = new URLSearchParams(searchParams)
                  if (c) next.set('category', c)
                  else next.delete('category')
                  setSearchParams(next, { replace: true })
                }}
              />
              <ScrollArea className="h-[610px] pr-3">
                {isLoading ? (
                  <div className="space-y-2">
                    {Array.from({ length: 8 }).map((_, index) => (
                      <Skeleton key={index} className="h-14 rounded-md" />
                    ))}
                  </div>
                ) : filteredDocs.length === 0 ? (
                  <div className="py-16 text-center text-sm text-muted-foreground">
                    暂无匹配文档
                  </div>
                ) : (
                  <div className="space-y-2">
                    {filteredDocs.map((doc) => (
                      <KnowledgeListItem
                        key={doc.id}
                        doc={doc}
                        active={selectedDoc?.id === doc.id}
                        onClick={() => setSelectedId(doc.id)}
                      />
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </div>

        <div className="col-span-4">
          <Card className="bg-card border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">文档详情</CardTitle>
            </CardHeader>
            <CardContent>
              {selectedDoc ? (
                <KnowledgeDetail doc={selectedDoc} />
              ) : (
                <div className="py-24 text-center text-sm text-muted-foreground">
                  选择左侧文档查看内容
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function KnowledgeListItem({
  doc,
  active,
  onClick,
}: {
  doc: KnowledgeDocument
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full rounded-md border p-2.5 text-left transition-colors ${
        active ? 'border-primary bg-primary/5' : 'border-border bg-background hover:border-primary/50'
      }`}
    >
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium leading-snug">{doc.title}</div>
        </div>
        <Badge variant="outline" className="shrink-0 border-0 bg-primary/15 px-1.5 py-0 text-[10px] text-primary">
          {doc.category}
        </Badge>
      </div>
      <p className="mt-1 line-clamp-1 text-[11px] leading-snug text-muted-foreground/80">
        {doc.preview || doc.content || '暂无内容'}
      </p>
      <div className="mt-1 flex items-center gap-2 text-[10px] text-muted-foreground/70">
        <span className="flex items-center gap-0.5">
          <Layers className="h-2.5 w-2.5" />
          {doc.chunk_count} 块
        </span>
        <span className="font-mono">{doc.id.slice(0, 8)}</span>
      </div>
    </button>
  )
}

function CategoryChips({
  categoryCount,
  activeCategory,
  onToggle,
}: {
  categoryCount: Record<string, number>
  activeCategory: string
  onToggle: (category: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const entries = Object.entries(categoryCount).sort((a, b) => b[1] - a[1])
  const LIMIT = 6
  const visible = expanded ? entries : entries.slice(0, LIMIT)
  const hidden = entries.length - LIMIT

  return (
    <div className="mb-3">
      <div className="flex flex-wrap items-center gap-1">
        <button
          type="button"
          onClick={() => onToggle('')}
          className={`rounded-full px-2 py-0.5 text-[10px] transition-colors ${
            !activeCategory
              ? 'bg-primary text-primary-foreground'
              : 'bg-secondary text-muted-foreground hover:bg-secondary/70'
          }`}
        >
          全部 · {Object.values(categoryCount).reduce((a, b) => a + b, 0)}
        </button>
        {visible.map(([name, count]) => (
          <button
            key={name}
            type="button"
            onClick={() => onToggle(name === activeCategory ? '' : name)}
            className={`max-w-[160px] truncate rounded-full px-2 py-0.5 text-[10px] transition-colors ${
              name === activeCategory
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-muted-foreground hover:bg-secondary/70'
            }`}
            title={name}
          >
            {name} · {count}
          </button>
        ))}
        {hidden > 0 && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-secondary/70"
          >
            {expanded ? '收起' : `+${hidden}`}
          </button>
        )}
      </div>
    </div>
  )
}

function KnowledgeDetail({ doc }: { doc: KnowledgeDocument }) {
  return (
    <div className="space-y-4">
      <div>
        <div className="mb-2 flex items-center gap-2">
          <FileText className="h-4 w-4 text-primary" />
          <h3 className="line-clamp-2 text-base font-semibold">{doc.title}</h3>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline" className="border-0 bg-primary/15 text-primary">
            {doc.category}
          </Badge>
          <Badge variant="outline" className="border-border bg-background">
            {doc.chunk_count} 个分块
          </Badge>
          {doc.source && (
            <Badge variant="outline" className="border-border bg-background">
              {doc.source}
            </Badge>
          )}
        </div>
      </div>

      <Separator className="bg-border" />

      <div>
        <div className="mb-2 text-xs font-medium text-muted-foreground">完整内容</div>
        <ScrollArea className="h-64 rounded-md border border-border bg-background p-3">
          <p className="whitespace-pre-wrap pr-3 text-sm leading-relaxed text-foreground/90">
            {doc.content || '暂无内容'}
          </p>
        </ScrollArea>
      </div>

      <div>
        <div className="mb-2 text-xs font-medium text-muted-foreground">分块明细</div>
        <ScrollArea className="h-60 pr-3">
          <div className="space-y-2">
            {doc.chunks.map((chunk) => (
              <div key={chunk.point_id} className="rounded-md border border-border bg-background p-3">
                <div className="mb-2 flex items-center justify-between text-[11px] text-muted-foreground">
                  <span>Chunk #{chunk.index + 1}</span>
                  <span className="font-mono">{chunk.point_id.slice(0, 12)}</span>
                </div>
                <p className="line-clamp-4 text-xs leading-relaxed text-foreground/80">
                  {chunk.content}
                </p>
              </div>
            ))}
          </div>
        </ScrollArea>
      </div>
    </div>
  )
}
