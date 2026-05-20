import { useState } from 'react'
import { useUploadKnowledge } from '@/hooks/useApi'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { BookOpen, Upload, CheckCircle2 } from 'lucide-react'

export function Knowledge() {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [category, setCategory] = useState('technical')
  const [success, setSuccess] = useState(false)

  const uploadMutation = useUploadKnowledge()

  const handleUpload = async () => {
    if (!title.trim() || !content.trim()) return
    try {
      await uploadMutation.mutateAsync({ title, content, category })
      setSuccess(true)
      setTitle('')
      setContent('')
      setTimeout(() => setSuccess(false), 3000)
    } catch {
      // error handled by mutation
    }
  }

  const sampleDocs = [
    { title: '系统崩溃排查手册', category: 'technical', content: '系统崩溃常见原因：1. 内存不足 2. 数据库连接池耗尽 3. 磁盘空间满...' },
    { title: '退款流程说明', category: 'billing', content: '退款流程：1. 用户提交退款申请 2. 客服审核 3. 财务确认 4. 3-5个工作日到账...' },
    { title: 'VIP用户服务协议', category: 'complaint', content: 'VIP用户享有优先处理权，投诉工单将在2小时内响应...' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-primary" />
          知识库管理
        </h2>
        <p className="text-sm text-muted-foreground mt-1">上传和管理 RAG 知识库文档</p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* 上传表单 */}
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
            <div className="flex gap-2">
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
          </CardContent>
        </Card>

        {/* 快速上传示例 */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">快速填充示例</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {sampleDocs.map((doc) => (
                <div
                  key={doc.title}
                  onClick={() => {
                    setTitle(doc.title)
                    setContent(doc.content)
                    setCategory(doc.category)
                  }}
                  className="p-3 rounded-md bg-background border border-border cursor-pointer hover:border-primary/50 transition-colors"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium">{doc.title}</span>
                    <Badge variant="outline" className="border-0 text-[10px] bg-primary/15 text-primary">
                      {doc.category}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-2">{doc.content}</p>
                </div>
              ))}
            </div>

            <Separator className="my-4 bg-border" />

            <div className="text-xs text-muted-foreground">
              <p className="font-medium mb-2">使用说明</p>
              <ul className="space-y-1 list-disc list-inside">
                <li>点击示例可自动填充表单</li>
                <li>文档会被自动分块并存入 Qdrant 向量库</li>
                <li>Processor Agent 处理工单时会检索相关知识</li>
                <li>分类标签有助于精准匹配检索</li>
              </ul>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
