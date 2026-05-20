import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { Settings2, Cpu, Bot, Shield, Zap } from 'lucide-react'

export function Settings() {
  const settings = [
    {
      group: 'LLM 模型配置',
      icon: Bot,
      items: [
        { label: 'Base URL', key: 'llm_base_url', value: 'https://ollama.com/v1', desc: 'OpenAI 兼容 API 地址' },
        { label: 'API Key', key: 'llm_api_key', value: 'ollama', desc: 'API 密钥（已配置环境变量）' },
        { label: '默认模型', key: 'llm_model', value: 'gemma3:12b', desc: '主处理模型' },
        { label: 'Embedding 模型', key: 'embedding_model', value: 'qwen3-embedding:4b', desc: '向量嵌入模型' },
        { label: 'Embedding 维度', key: 'embedding_dim', value: '2560', desc: '向量维度' },
      ],
    },
    {
      group: '模型路由',
      icon: Zap,
      items: [
        { label: '分类任务', key: 'route_classify', value: 'gemma3:12b', desc: '工单分类使用的模型' },
        { label: '处理任务', key: 'route_process', value: 'gemma3:12b', desc: '工单处理使用的模型' },
        { label: '审核任务', key: 'route_review', value: 'gemma3:12b', desc: '质量审核使用的模型' },
        { label: '降级模型', key: 'fallback_model', value: 'gemma3:12b', desc: '模型不可用时的降级选择' },
      ],
    },
    {
      group: '处理策略',
      icon: Shield,
      items: [
        { label: '最大重试次数', key: 'max_retries', value: '3', desc: 'Agent 调用失败时的最大重试次数' },
        { label: '审核通过阈值', key: 'review_threshold', value: '0.7', desc: '审核评分 ≥ 此值时通过（0-1）' },
        { label: 'ReAct 最大迭代', key: 'max_react_iterations', value: '10', desc: 'ReAct 循环最大迭代次数' },
        { label: '上下文窗口', key: 'max_messages', value: '20', desc: '保留的最大消息轮数' },
        { label: '最大并发', key: 'max_concurrency', value: '5', desc: '批量工单最大并发数' },
      ],
    },
    {
      group: '基础设施',
      icon: Cpu,
      items: [
        { label: 'Qdrant 地址', key: 'qdrant_url', value: 'http://qdrant:6333', desc: '向量数据库地址' },
        { label: 'Qdrant 集合', key: 'qdrant_collection', value: 'knowledge_base', desc: '知识库集合名称' },
        { label: '缓存 TTL', key: 'cache_ttl', value: '300s', desc: 'LLM 响应缓存有效期' },
        { label: 'Checkpoint TTL', key: 'checkpoint_ttl', value: '86400s (24h)', desc: '检查点有效期' },
      ],
    },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Settings2 className="w-5 h-5 text-primary" />
          系统设置
        </h2>
        <p className="text-sm text-muted-foreground mt-1">查看和管理系统配置（当前为只读）</p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {settings.map((group) => (
          <Card key={group.group} className="bg-card border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <group.icon className="w-4 h-4 text-primary" />
                {group.group}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {group.items.map((item, i) => (
                <div key={item.key}>
                  {i > 0 && <Separator className="bg-border mb-3" />}
                  <div className="flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <p className="text-sm font-medium">{item.label}</p>
                      <p className="text-[11px] text-muted-foreground">{item.desc}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {item.key === 'llm_api_key' ? (
                        <Badge variant="outline" className="border-0 bg-success/15 text-success text-xs">
                          已配置
                        </Badge>
                      ) : (
                        <code className="text-xs font-mono bg-background px-2 py-1 rounded border border-border text-foreground">
                          {item.value}
                        </code>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* 系统信息 */}
      <Card className="bg-card border-border">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">系统信息</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-4 gap-4 text-center">
            <div className="bg-background rounded-md p-4 border border-border">
              <p className="text-lg font-bold text-primary">v1.0.0</p>
              <p className="text-[11px] text-muted-foreground">系统版本</p>
            </div>
            <div className="bg-background rounded-md p-4 border border-border">
              <p className="text-lg font-bold text-success">4</p>
              <p className="text-[11px] text-muted-foreground">Agent 数量</p>
            </div>
            <div className="bg-background rounded-md p-4 border border-border">
              <p className="text-lg font-bold text-warning">10</p>
              <p className="text-[11px] text-muted-foreground">LangGraph 节点</p>
            </div>
            <div className="bg-background rounded-md p-4 border border-border">
              <p className="text-lg font-bold text-primary">SQLite</p>
              <p className="text-[11px] text-muted-foreground">数据存储</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
