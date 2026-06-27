import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { CategoryBadge, PriorityBadge, StatusBadge } from '@/components/layout/StatusBadge'
import type { ReviewDetail as ReviewDetailType } from '@/types'

interface Props {
  detail: ReviewDetailType
}

export function ReviewDetailPanel({ detail }: Props) {
  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between gap-2 text-sm">
          <span className="flex items-center gap-2">
            <span className="font-mono">{detail.ticket_id}</span>
            <span className="text-muted-foreground">·</span>
            <StatusBadge status={detail.status} />
          </span>
          <span className="text-xs text-muted-foreground">
            重试次数：{detail.retry_count}
            {detail.review_score != null && (
              <span className="ml-2">评分 {detail.review_score.toFixed(2)}</span>
            )}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          {detail.category && <CategoryBadge category={detail.category} />}
          {detail.priority && <PriorityBadge priority={detail.priority} />}
        </div>
        <Separator className="bg-border" />
        <div>
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">工单原文</p>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{detail.content}</p>
        </div>
      </CardContent>
    </Card>
  )
}
