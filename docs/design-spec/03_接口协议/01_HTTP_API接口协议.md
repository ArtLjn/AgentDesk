# HTTP API 接口协议

## 1. 基本约定

后端接口统一以 `/api` 为前缀。请求和响应默认使用 JSON。接口实现位置为 `src/multi_agent_system/api/routes.py`。

## 2. 工单接口

### 2.1 创建工单

`POST /api/tickets`

请求体：

```json
{
  "content": "无法登录系统，点击登录按钮后报错 500",
  "user_id": "U001"
}
```

响应：

```json
{
  "ticket_id": "TK-20260624-001",
  "status": "received"
}
```

说明：接口立即返回，后台异步执行 LangGraph 工作流。

### 2.2 批量创建工单

`POST /api/tickets/batch`

请求体：

```json
{
  "tickets": [
    {
      "content": "系统报错",
      "user_id": "U001"
    },
    {
      "content": "我想咨询套餐价格",
      "user_id": "U002"
    }
  ]
}
```

响应：

```json
{
  "results": {
    "ticket_0": {
      "ticket_id": "TK-20260624-001",
      "status": "received"
    }
  }
}
```

### 2.3 查询工单详情

`GET /api/tickets/{ticket_id}`

响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ticket_id` | string | 工单 ID |
| `content` | string | 工单内容 |
| `category` | string/null | 分类 |
| `priority` | string/null | 优先级 |
| `processing_result` | string/null | 处理结果 |
| `review_score` | number/null | 审核评分 |
| `retry_count` | number | 重试次数 |
| `status` | string | 当前状态 |
| `error` | string/null | 错误信息 |
| `created_at` | string | 创建时间 |

### 2.4 查询工单列表

`GET /api/tickets?status=&category=&limit=&offset=`

查询参数：

| 参数 | 说明 |
| --- | --- |
| `status` | 可选，按状态过滤 |
| `category` | 可选，按分类过滤 |
| `limit` | 返回数量，默认 20，最大 100 |
| `offset` | 分页偏移 |

### 2.5 提交反馈

`POST /api/tickets/{ticket_id}/feedback`

请求体：

```json
{
  "satisfied": true
}
```

响应：

```json
{
  "status": "ok",
  "ticket_id": "TK-20260624-001",
  "satisfied": true
}
```

## 3. 知识库接口

### 3.1 上传知识文档

`POST /api/knowledge`

请求体：

```json
{
  "title": "登录失败处理手册",
  "content": "当用户无法登录时，先检查账号状态和密码错误次数。",
  "category": "technical"
}
```

响应：

```json
{
  "status": "ok",
  "chunks_added": 1,
  "message": "文档已上传"
}
```

## 4. 统计接口

### 4.1 获取统计数据

`GET /api/analytics`

响应包含：

- `category_distribution`
- `priority_distribution`
- `resolution_stats`
- `daily_stats`
- `efficiency`
- `evaluation`

## 5. 执行追踪接口

### 5.1 查询工单 Trace

`GET /api/tickets/{ticket_id}/trace`

### 5.2 查询 Trace 列表

`GET /api/traces?status=&limit=&offset=`

### 5.3 查询 Trace 统计

`GET /api/traces/{trace_id}/stats`

## 6. 人工审核接口（v1.0 新增）

详细设计参见 [01_正式设计/09_人工审核工作台设计.md](../01_正式设计/09_人工审核工作台设计.md)。

### 6.1 查询待审核队列

`GET /api/reviews/queue`

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `trigger_type` | string | 否 | `escalate` / `review_failed` / `error_fallback` / `user_request` |
| `category` | string | 否 | 工单分类 |
| `priority` | string | 否 | 工单优先级 |
| `limit` | int | 否 | 默认 20，上限 100 |
| `offset` | int | 否 | 默认 0 |

响应：

```json
{
  "queue": [
    {
      "review_id": "HR-TK-20260627-001",
      "ticket_id": "TK-20260627-001",
      "trigger_type": "escalate",
      "trigger_reason": "投诉类工单",
      "content_preview": "我对昨天购买的...",
      "category": "complaint",
      "priority": "P1",
      "ai_suggestion": {
        "recommended_decision": "reprocess",
        "confidence": 0.72,
        "reasoning": "...",
        "key_concerns": ["..."]
      },
      "waiting_seconds": 1200,
      "created_at": "2026-06-27T10:00:00"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

### 6.2 查询审核详情

`GET /api/reviews/{ticket_id}`

返回该工单的完整审核上下文：原文、分类、优先级、AI 处理结果、trace 摘要、历史决策、当前 AI 建议。

### 6.3 提交审核决策

`POST /api/reviews/{ticket_id}/decision`

请求体：

```json
{
  "decision": "approve | reject | rewrite | reprocess",
  "decision_reason": "审核员填写的理由（必填）",
  "rewritten_result": "仅 decision=rewrite 时必填",
  "reviewer_id": "reviewer-001"
}
```

响应：

```json
{
  "status": "ok",
  "ticket_id": "TK-...",
  "next_node": "notify | process | complete",
  "workflow_resumed": true
}
```

行为：校验工单状态为 `pending_human_review` → 写入决策 → 触发 `apply_human_decision` 节点 → 推送 WebSocket `review_decided` 事件。

错误码：

| HTTP | 错误码 | 场景 |
| --- | --- | --- |
| 404 | `TICKET_NOT_FOUND` | 工单不存在 |
| 409 | `TICKET_NOT_PENDING` | 工单不在待审核状态 |
| 400 | `REWRITE_RESULT_REQUIRED` | decision=rewrite 但未提供 rewritten_result |
| 400 | `DECISION_REASON_REQUIRED` | 未填写决策理由 |

### 6.4 审核统计

`GET /api/reviews/stats`

```json
{
  "pending_count": 3,
  "decided_today": 12,
  "decision_distribution": {"approve": 7, "rewrite": 3, "reprocess": 1, "reject": 1},
  "avg_decision_seconds": 320,
  "ai_adoption_rate": 0.58
}
```

`ai_adoption_rate` 表示审核员最终决策与 AI 建议一致的比例，是论文的核心评估指标。
