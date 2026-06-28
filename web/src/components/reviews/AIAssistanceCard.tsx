import { Sparkles, AlertCircle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Markdown } from '@/components/ui/markdown'
import type { AISuggestion } from '@/types'
import { decisionMeta } from './reviewUtils'
import { cn } from '@/lib/utils'

interface Props {
  suggestion: AISuggestion | null
}

export function AIAssistanceCard({ suggestion }: Props) {
  if (!suggestion) {
    return (
      <Card className="bg-card border-border">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Sparkles className="h-4 w-4 text-primary" />
            AI 辅助决策建议
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">该工单无 AI 建议（可能由用户主动请求审核触发）。</p>
        </CardContent>
      </Card>
    )
  }

  const meta = decisionMeta[suggestion.recommended_decision]
  const highConfidence = suggestion.confidence > 0.7

  return (
    <Card
      className={cn(
        'bg-card border-border ring-1 transition-all',
        highConfidence ? `border-success/40 ring-success/30` : 'ring-transparent',
      )}
    >
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between gap-2 text-sm">
          <span className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            AI 辅助决策建议
          </span>
          <span
            className={cn(
              'rounded-sm px-1.5 py-0.5 text-[10px] font-medium',
              highConfidence ? 'bg-success/15 text-success' : 'bg-muted text-muted-foreground',
            )}
          >
            高置信 {Math.round(suggestion.confidence * 100)}%
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">推荐决策</span>
          <span className={cn('rounded-sm px-2 py-0.5 text-xs font-medium', meta.color)}>
            {meta.label}
          </span>
          <span className="ml-auto font-mono text-[11px] text-muted-foreground tabular-nums">
            置信度 {suggestion.confidence.toFixed(2)}
          </span>
        </div>

        <div>
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">推理</p>
          <div className="rounded-md border border-border bg-background p-2.5">
            <Markdown>{suggestion.reasoning}</Markdown>
          </div>
        </div>

        {suggestion.key_concerns?.length > 0 && (
          <div>
            <p className="mb-1 flex items-center gap-1 text-[10px] uppercase tracking-wide text-muted-foreground">
              <AlertCircle className="h-3 w-3" />
              关键关注点
            </p>
            <ul className="space-y-1">
              {suggestion.key_concerns.map((c, i) => (
                <li
                  key={i}
                  className="flex items-start gap-1.5 rounded-md border border-border bg-background px-2 py-1 text-xs"
                >
                  <span className="mt-0.5 inline-block h-1 w-1 rounded-full bg-warning shrink-0" />
                  <span className="text-foreground/80">{c}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
