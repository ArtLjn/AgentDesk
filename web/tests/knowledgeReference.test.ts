import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildKnowledgeSearchParams,
  filterKnowledgeDocuments,
} from '../src/lib/knowledgeReference.ts'

const docs = [
  {
    id: 'doc-1',
    title: '账务处理指南',
    category: 'billing',
    content: '财务 -> 账单查询。核对每笔扣费对应的订单记录和服务周期。',
    preview: '财务 -> 账单查询。核对每笔扣费对应的订单记录和服务周期。',
    chunk_count: 1,
    chunks: [],
  },
  {
    id: 'doc-2',
    title: '系统崩溃排查手册',
    category: 'technical',
    content: '检查服务端日志、资源占用和依赖服务状态。',
    preview: '检查服务端日志、资源占用和依赖服务状态。',
    chunk_count: 1,
    chunks: [],
  },
]

test('知识库参考跳转不使用不可靠分类硬过滤', () => {
  const reference = [
    '检索到以下知识片段：',
    '1. 标题: 账务处理指南；分类: billing-guide；相似度: 0.75',
    '内容: > 财务 -> 账单查询） 2. 核对每笔扣费对应的订单记录和服务周期',
  ].join('\n')

  const params = buildKnowledgeSearchParams(reference)

  assert.equal(params.get('q'), '账务处理指南')
  assert.equal(params.has('category'), false)
})

test('知识库搜索能用标题命中分类别名不同的文档', () => {
  const matched = filterKnowledgeDocuments(docs, {
    query: '账务处理指南',
    category: 'billing-guide',
  })

  assert.deepEqual(matched.map((doc) => doc.id), ['doc-1'])
})
