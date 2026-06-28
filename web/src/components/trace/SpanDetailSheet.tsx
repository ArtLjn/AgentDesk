/**
 * 节点详情侧拉面板。
 * 点击甘特图/决策卡片中的节点后弹出，显示完整的 input/output/metadata。
 * 参考 admin-web TraceMonitor 的 Drawer 部分。
 */
import type { Span } from '@/types'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { DecisionCard, type DecisionData } from './DecisionCard'
import {
  formatDuration,
  getSpanStatusLabel,
  getSpanTypeColor,
  getSpanTypeLabel,
} from './spanTypes'
import { extractFields, FieldList } from './spanFormat'

export interface SpanDetailSheetProps {
  span: Span | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function SpanDetailSheet({ span, open, onOpenChange }: SpanDetailSheetProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-[640px] overflow-y-auto bg-card border-border">
        {span && <SpanDetailBody span={span} />}
      </SheetContent>
    </Sheet>
  )
}

function SpanDetailBody({ span }: { span: Span }) {
  const color = getSpanTypeColor(span.span_type)
  const inputFields = extractFields(span.input_data)
  const outputFields = extractFields(span.output_data)
  const metaFields = extractFields(span.metadata)
  const metadata = (span.metadata || {}) as Record<string, unknown>
  const decision = (metadata.decision || null) as DecisionData | null

  return (
    <div className="space-y-5">
      <SheetHeader>
        <div className="flex items-center gap-2">
          <span className="inline-block h-3 w-3 rounded-full" style={{ background: color }} />
          <SheetTitle className="text-base font-mono">{span.name}</SheetTitle>
        </div>
        <SheetDescription className="sr-only">节点详情</SheetDescription>
      </SheetHeader>

      {/* 元信息条 */}
      <div className="flex flex-wrap items-center gap-2 text-[12px]">
        <Badge
          variant="outline"
          className="border-0 px-2 py-0.5 text-[11px] font-medium"
          style={{ background: `${color}20`, color }}
        >
          {getSpanTypeLabel(span.span_type)}
        </Badge>
        <Badge
          variant="outline"
          className="border-0 px-2 py-0.5 text-[11px] font-medium"
          style={{ background: `${getSpanTypeColor(span.span_type)}20` }}
        >
          {getSpanStatusLabel(span.status)}
        </Badge>
        <span className="font-mono text-muted-foreground">
          耗时 {formatDuration(span.duration)}
        </span>
        <span className="font-mono text-[11px] text-muted-foreground/70">
          #{span.span_id.slice(0, 12)}
        </span>
      </div>

      {/* 决策点 */}
      {decision && (
        <section>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            决策点
          </h4>
          <DecisionCard decision={decision} />
        </section>
      )}

      {/* 输入 */}
      {inputFields.length > 0 && (
        <section>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            输入数据
          </h4>
          <FieldList fields={inputFields} />
        </section>
      )}

      {/* 输出 */}
      {outputFields.length > 0 && (
        <section>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            输出数据
          </h4>
          <FieldList fields={outputFields} />
        </section>
      )}

      {/* 元数据 */}
      {metaFields.length > 0 && (
        <section>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            元数据
          </h4>
          <FieldList fields={metaFields} />
        </section>
      )}

      {inputFields.length === 0 && outputFields.length === 0 && metaFields.length === 0 && !decision && (
        <p className="py-8 text-center text-sm text-muted-foreground">
          该节点没有记录输入/输出数据
        </p>
      )}
    </div>
  )
}
