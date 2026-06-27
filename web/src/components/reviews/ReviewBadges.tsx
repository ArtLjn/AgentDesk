import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { TriggerType } from '@/types'
import { triggerLabels, triggerStyles } from './reviewUtils'

export function TriggerBadge({ trigger }: { trigger: TriggerType | string }) {
  return (
    <Badge
      variant="outline"
      className={cn('border-0 font-medium', triggerStyles[trigger] || 'bg-secondary text-muted-foreground')}
    >
      {triggerLabels[trigger] || trigger}
    </Badge>
  )
}
