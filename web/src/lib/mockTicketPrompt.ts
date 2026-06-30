import type { KnowledgeDocument } from '@/types'

const INTENT_BY_CATEGORY: Record<string, string[]> = {
  billing: ['我想咨询账务处理', '请帮我确认费用或发票问题', '我需要处理账单相关问题'],
  technical: ['我遇到了系统使用问题', '请帮我排查技术故障', '我需要技术支持'],
  complaint: ['我要反馈一个体验问题', '请帮我处理这个投诉', '我对当前处理结果不满意'],
  inquiry: ['我想咨询操作流程', '请告诉我该怎么操作', '我需要了解相关规则'],
}

const FALLBACK_INTENTS = [
  '我想咨询这个功能的处理流程',
  '请帮我确认这个问题该怎么处理',
  '我需要根据知识库内容完成一次操作',
]

export function buildKnowledgeMockTicketPrompt(
  documents: KnowledgeDocument[],
  seed = Date.now(),
): string {
  const candidates = documents.filter((doc) => getDocumentText(doc))
  if (candidates.length === 0) return ''

  const doc = candidates[Math.abs(seed) % candidates.length]
  const text = normalizeText(getDocumentText(doc))
  const summary = text.slice(0, 72)
  const intents = INTENT_BY_CATEGORY[doc.category] || FALLBACK_INTENTS
  const intent = intents[Math.abs(seed + doc.title.length) % intents.length]

  return `${intent}：关于“${doc.title}”，我看到了“${summary}”，但不确定具体应该怎么做，请帮我给出清晰步骤。`
}

function getDocumentText(doc: KnowledgeDocument): string {
  return doc.preview || doc.content || doc.chunks?.map((chunk) => chunk.content).join(' ') || ''
}

function normalizeText(value: string): string {
  return value
    .replace(/\s+/g, ' ')
    .replace(/[#*_`>[\](){}]/g, '')
    .trim()
}
