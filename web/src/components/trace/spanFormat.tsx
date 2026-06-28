/* eslint-disable react-refresh/only-export-components */
/**
 * 把 Span 的 input_data / output_data / metadata 渲染成人类可读的字段列表，
 * 而不是一坨原始 JSON。参考 admin-web SkillOutputFormatter 的思路。
 *
 * 渲染策略：
 *  - 已知的语义字段（prompt/response/tool_name/...）单独高亮显示
 *  - 其余字段作为键值对罗列
 *  - 长文本（>200 字）默认折叠，点击展开
 *  - 长文本字段用 Markdown 渲染（支持标题、列表、代码块、表格）
 */
import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { Markdown } from '@/components/ui/markdown'

export interface FieldItem {
  key: string
  label: string
  value: unknown
  /** 高亮显示（重要字段） */
  highlight?: boolean
  /** 渲染类型 */
  kind?: 'text' | 'long_text' | 'json' | 'list' | 'number'
}

/** 已知语义字段的中文标签和渲染方式 */
const KNOWN_FIELDS: Record<string, { label: string; kind?: FieldItem['kind']; highlight?: boolean }> = {
  // LLM 调用
  prompt: { label: 'Prompt', kind: 'long_text', highlight: true },
  system_prompt: { label: '系统 Prompt', kind: 'long_text', highlight: true },
  response: { label: '回复', kind: 'long_text', highlight: true },
  model: { label: '模型', highlight: true },
  temperature: { label: '温度' },
  max_tokens: { label: '最大 tokens' },

  // 工具调用
  tool_name: { label: '工具名称', highlight: true },
  tool_args: { label: '工具参数', kind: 'json' },
  args: { label: '参数', kind: 'json' },
  result: { label: '返回结果', kind: 'long_text', highlight: true },
  query: { label: '查询', highlight: true },

  // 工单流转
  content: { label: '工单内容', kind: 'long_text', highlight: true },
  category: { label: '分类', highlight: true },
  priority: { label: '优先级', highlight: true },
  result_answer: { label: '处理结论', kind: 'long_text', highlight: true },
  final_answer: { label: '最终结论', kind: 'long_text', highlight: true },
  answer: { label: '结论', kind: 'long_text', highlight: true },
  processing_result: { label: '处理结果', kind: 'long_text', highlight: true },
  review_score: { label: '审核评分', highlight: true },
  references: { label: '知识库引用', kind: 'list' },

  // ReAct
  thought: { label: '思考', kind: 'long_text', highlight: true },
  action: { label: '行动', highlight: true },
  observation: { label: '观察', kind: 'long_text' },
  iteration: { label: '轮次' },

  // 元数据
  error: { label: '错误信息', kind: 'long_text', highlight: true },
  reason: { label: '原因', kind: 'long_text' },
}

/**
 * 把任意 data 对象转成结构化字段列表。
 * 已知字段用中文标签，未知字段保留原 key。
 */
export function extractFields(data: Record<string, unknown> | null | undefined): FieldItem[] {
  if (!data || typeof data !== 'object') return []
  return Object.entries(data).map(([key, value]) => {
    const known = KNOWN_FIELDS[key]
    return {
      key,
      label: known?.label ?? key,
      value,
      highlight: known?.highlight,
      kind: known?.kind ?? inferKind(value),
    }
  })
}

function inferKind(value: unknown): FieldItem['kind'] {
  if (value == null) return 'text'
  if (Array.isArray(value)) return value.length > 0 ? 'list' : 'text'
  if (typeof value === 'object') return 'json'
  if (typeof value === 'number') return 'number'
  if (typeof value === 'string' && value.length > 120) return 'long_text'
  return 'text'
}

export function FieldList({ fields }: { fields: FieldItem[] }) {
  if (fields.length === 0) return null
  return (
    <div className="space-y-2">
      {fields.map((field) => (
        <FieldRow key={field.key} field={field} />
      ))}
    </div>
  )
}

function FieldRow({ field }: { field: FieldItem }) {
  const isLong = field.kind === 'long_text' && typeof field.value === 'string' && field.value.length > 200
  const [expanded, setExpanded] = useState(false)

  return (
    <div className={`rounded-md border ${field.highlight ? 'border-primary/30 bg-primary/5' : 'border-border bg-background/60'} px-3 py-2`}>
      <div className="flex items-center gap-2 mb-1">
        {isLong && (
          <button type="button" onClick={() => setExpanded(!expanded)} className="text-muted-foreground hover:text-foreground">
            {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          </button>
        )}
        <span className={`text-[11px] font-medium uppercase tracking-wide ${field.highlight ? 'text-primary' : 'text-muted-foreground'}`}>
          {field.label}
        </span>
      </div>
      <FieldValue field={field} expanded={expanded} />
    </div>
  )
}

function FieldValue({ field, expanded }: { field: FieldItem; expanded: boolean }) {
  const { value, kind } = field
  if (value == null) return <span className="text-xs text-muted-foreground/60">-</span>

  if (kind === 'list' && Array.isArray(value)) {
    return (
      <ul className="ml-3 list-disc space-y-0.5 text-[12px] text-foreground/80">
        {value.map((item, i) => (
          <li key={i} className="whitespace-pre-wrap break-words">
            {typeof item === 'string' ? truncate(item, expanded, 200) : JSON.stringify(item, null, 2)}
          </li>
        ))}
      </ul>
    )
  }

  if (kind === 'json' && typeof value === 'object') {
    return (
      <pre className="overflow-x-auto rounded bg-card/60 p-2 text-[11px] text-foreground/80 whitespace-pre-wrap break-all">
        {JSON.stringify(value, null, 2)}
      </pre>
    )
  }

  if (kind === 'long_text' && typeof value === 'string') {
    const display = truncate(value, expanded, 200)
    const hasMarkdown = /(^|\n)\s*(#{1,6}\s|[-*+]\s|\d+\.\s|```|>|#{1,3}\s)/.test(value)
    if (hasMarkdown) {
      return (
        <div className="rounded bg-card/40">
          <Markdown>{display}</Markdown>
        </div>
      )
    }
    return (
      <p className="text-[12px] text-foreground/90 leading-relaxed whitespace-pre-wrap break-words">
        {display}
      </p>
    )
  }

  return <span className="text-[12px] text-foreground/90 tabular-nums">{String(value)}</span>
}

function truncate(text: string, expanded: boolean, max: number): string {
  if (expanded || text.length <= max) return text
  return `${text.slice(0, max)}... (+${text.length - max} 字)`
}
