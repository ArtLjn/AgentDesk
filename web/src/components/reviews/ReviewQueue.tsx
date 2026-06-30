import { RefreshCw } from 'lucide-react'
import type { ReviewQueueItem as ReviewQueueItemType } from '@/types'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ReviewQueueItem } from './ReviewQueueItem'

interface Props {
  items: ReviewQueueItemType[]
  selectedId: string | null
  loading: boolean
  error?: Error | null
  onSelect: (ticketId: string) => void
  onRefresh: () => void
}

export function ReviewQueue({ items, selectedId, loading, error, onSelect, onRefresh }: Props) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between px-1 pb-2">
        <h3 className="text-sm font-semibold">
          待审核队列
          <span className="ml-1.5 rounded-sm bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
            {items.length}
          </span>
        </h3>
        <Button variant="ghost" size="icon-sm" onClick={onRefresh} aria-label="刷新队列">
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      </div>

      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-lg" />)
        ) : error ? (
          <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-xs text-destructive">
            加载失败：{error.message}
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-8 text-center text-xs text-muted-foreground">
            队列为空，喝杯咖啡。
          </div>
        ) : (
          items.map((item) => (
            <ReviewQueueItem
              key={item.review_id || item.ticket_id}
              item={item}
              active={selectedId === item.ticket_id}
              onSelect={onSelect}
            />
          ))
        )}
      </div>
    </div>
  )
}
