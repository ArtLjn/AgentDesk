import assert from 'node:assert/strict'
import test from 'node:test'

import { buildKnowledgeMockTicketPrompt } from '../src/lib/mockTicketPrompt.ts'
import type { KnowledgeDocument } from '../src/types/index.ts'

const docs: KnowledgeDocument[] = [
  {
    id: 'doc-1',
    title: '发票开具流程',
    category: 'billing',
    content: '登录控制台后进入发票管理，选择已完成订单并填写抬头。',
    preview: '登录控制台后进入发票管理，选择已完成订单并填写抬头。',
    chunk_count: 1,
    chunks: [],
  },
]

test('根据知识库文档生成真实用户口吻的 mock 工单', () => {
  const prompt = buildKnowledgeMockTicketPrompt(docs, 0)

  assert.match(prompt, /发票开具流程/)
  assert.match(prompt, /登录控制台/)
  assert.match(prompt, /请帮我/)
  assert.ok(prompt.length >= 30)
})

test('知识库为空时返回空字符串，交给页面走兜底示例', () => {
  assert.equal(buildKnowledgeMockTicketPrompt([], 0), '')
})
