# HTTP API 接口协议

## 1. 基本约定

后端业务接口统一以 `/api` 为前缀。请求和响应默认使用 JSON。接口实现位置为 `src/multi_agent_system/api/routes.py`，鉴权接口位于 `src/multi_agent_system/api/auth_routes.py`。

业务路由默认要求登录；当配置项 `auth_enabled=false` 时，`require_login` 会自动放行，便于本地演示。

## 2. 鉴权接口

### 2.1 登录

`POST /api/auth/login`

请求体：

```json
{
  "username": "admin",
  "password": "password"
}
```

响应：

```json
{
  "username": "admin",
  "logged_in": true
}
```

说明：登录成功后后端写入 `agentdesk_session` cookie。密码使用 bcrypt 哈希校验，明文密码不应进入仓库。

### 2.2 退出登录

`POST /api/auth/logout`

响应：

```json
{
  "logged_out": true
}
```

### 2.3 当前登录状态

`GET /api/auth/me`

响应：

```json
{
  "logged_in": true,
  "username": "admin",
  "auth_enabled": true
}
```

## 3. 工单接口

### 3.1 创建工单

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

说明：接口会先调用 `TicketIntentAgent` 理解自然语言工单，提取分类、优先级、影响范围等信息并格式化正文；随后立即返回，后台异步执行 LangGraph 工作流。

### 3.2 批量创建工单

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

### 3.3 查询工单详情

`GET /api/tickets/{ticket_id}`

响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ticket_id` | string | 工单 ID |
| `content` | string | 工单内容 |
| `category` | string/null | 分类 |
| `priority` | string/null | 优先级 |
| `processing_result` | string/null | 处理结果 |
| `references` | array | 知识库引用列表 |
| `review_score` | number/null | 审核评分 |
| `retry_count` | number | 重试次数 |
| `status` | string | 当前状态 |
| `error` | string/null | 错误信息 |
| `created_at` | string | 创建时间 |

### 3.4 查询工单列表

`GET /api/tickets?status=&category=&limit=&offset=`

查询参数：

| 参数 | 说明 |
| --- | --- |
| `status` | 可选，按状态过滤 |
| `category` | 可选，按分类过滤 |
| `limit` | 返回数量，默认 20，最大 100 |
| `offset` | 分页偏移 |

### 3.5 提交反馈

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

说明：当 `satisfied=false` 且工单已完成时，系统会创建 `user_request` 类型人工审核单，并将工单状态转为 `pending_human_review`。

### 3.6 查询工单沟通记录

`GET /api/tickets/{ticket_id}/messages`

响应：

```json
[
  {
    "message_id": "TM-20260629-001",
    "ticket_id": "TK-20260629-001",
    "sender_type": "reviewer",
    "sender_id": "reviewer-001",
    "content": "请补充订单号和支付流水号",
    "metadata": {"source": "request_info"},
    "created_at": "2026-06-29T10:00:00"
  }
]
```

说明：该接口用于工单详情页展示审核员请求补充和用户回复。工单不存在时返回 404。

### 3.7 提交用户补充信息

`POST /api/tickets/{ticket_id}/messages`

请求体：

```json
{
  "content": "订单号是 202606290001，支付流水号是 PAY123456",
  "sender_id": "user-001"
}
```

响应：

```json
{
  "status": "ok",
  "ticket_id": "TK-20260629-001",
  "next_node": "complete",
  "workflow_resumed": true,
  "ticket_status": "completed"
}
```

行为：

1. 校验工单存在。
2. 校验工单状态必须为 `waiting_user_input`，否则返回 409。
3. 写入 `ticket_messages`，`sender_type=user`。
4. 调用 `resume_from_user_input`，读取沟通记录构造 `conversation_context`。
5. 从 `process` 节点恢复工作流，并通过 WebSocket 推送状态更新。

## 4. 知识库接口

### 4.1 查询知识库文档

`GET /api/knowledge?limit=&offset=`

响应：

```json
{
  "documents": [
    {
      "id": "doc-001",
      "title": "登录失败处理手册",
      "category": "technical",
      "source": null,
      "content": "完整内容",
      "preview": "内容预览",
      "chunk_count": 2,
      "chunks": [
        {
          "index": 0,
          "content": "分块内容",
          "point_id": "qdrant-point-id"
        }
      ]
    }
  ],
  "count": 1,
  "next_offset": null
}
```

说明：Qdrant 不可用时返回 503。

### 4.2 上传知识文档

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

## 5. 设置与统计接口

### 5.1 获取系统设置摘要

`GET /api/settings`

响应包含 LLM、Embedding、Qdrant、缓存、重试、审核阈值、并发、模型路由和 API 端口等只读配置摘要。敏感字段只返回是否已配置，不返回完整密钥。

### 5.2 获取统计数据

`GET /api/analytics`

响应包含：

- `category_distribution`
- `priority_distribution`
- `resolution_stats`
- `daily_stats`
- `efficiency`
- `evaluation`

## 6. 执行追踪接口

### 6.1 查询工单 Trace

`GET /api/tickets/{ticket_id}/trace`

响应包含 trace 基本信息、工单摘要、分类、优先级、处理结果、引用数量和 `spans` 树。

### 6.2 查询 Trace 列表

`GET /api/traces?status=&limit=&offset=`

### 6.3 查询 Trace 统计

`GET /api/traces/{trace_id}/stats`

### 6.4 查询 Trace 决策点

`GET /api/traces/{trace_id}/decisions`

响应：

```json
{
  "trace_id": "tr-001",
  "decision_count": 2,
  "decisions": [
    {
      "span_id": "sp-001",
      "span_name": "classify",
      "span_type": "node",
      "decision_type": "routing",
      "trigger": {"content_preview": "..."},
      "options_count": 4,
      "options": [],
      "selection_value": "technical",
      "confidence": 0.92,
      "reason": "登录失败属于技术问题",
      "start_time": 1710000000.0,
      "duration": 0.8
    }
  ]
}
```

说明：该接口从 `spans.metadata.decision` 中提取分类、审核、重试边界等决策语义。

## 7. 人工审核接口

详细设计参见 [01_正式设计/09_人工审核工作台设计.md](../01_正式设计/09_人工审核工作台设计.md)。

### 7.1 查询待审核队列

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

### 7.2 查询审核详情

`GET /api/reviews/{ticket_id}`

返回该工单的完整审核上下文：原文、分类、优先级、AI 处理结果、trace 摘要、历史决策、当前 AI 建议。

### 7.3 提交审核决策

`POST /api/reviews/{ticket_id}/decision`

请求体：

```json
{
  "decision": "approve | reject | rewrite | reprocess | request_info",
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
  "next_node": "notify | process | complete | waiting_user_input",
  "workflow_resumed": true
}
```

行为：

- `approve`：沿用当前 `processing_result`，恢复到 `notify → complete`。
- `rewrite`：用 `rewritten_result` 覆盖处理结果，恢复到 `notify → complete`。
- `reprocess`：清空处理结果和重试次数，恢复到 `process`。
- `reject`：标记驳回并进入 `complete`。
- `request_info`：调用 `pause_for_user_input`，工单进入 `waiting_user_input`，写入一条审核员补充请求消息，本次不恢复自动工作流。

校验规则：

- 工单不存在返回 404。
- 工单状态不是 `pending_human_review` 返回 409。
- `decision_reason` 必填且不能为空白。
- `decision=rewrite` 时 `rewritten_result` 必填。
- `decision=request_info` 时 `decision_reason` 即展示给用户的补充说明。

错误码：

| HTTP | 错误码 | 场景 |
| --- | --- | --- |
| 404 | `detail` 文本 | 工单不存在 |
| 409 | `detail` 文本 | 工单不在待审核状态 |
| 422 | Pydantic 校验错误 | decision_reason 为空，或 rewrite 未提供 rewritten_result |

### 7.4 审核统计

`GET /api/reviews/stats`

```json
{
  "pending_count": 3,
  "decided_today": 12,
  "decision_distribution": {"approve": 7, "rewrite": 3, "reprocess": 1, "reject": 1, "request_info": 2},
  "avg_decision_seconds": 320,
  "ai_adoption_rate": 0.58
}
```

`ai_adoption_rate` 表示审核员最终决策与 AI 建议一致的比例，是论文的核心评估指标。

## 8. 健康检查与指标接口

这些接口由 `api/app.py` 注册，不带 `/api` 前缀。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 服务健康状态、缓存和模型路由摘要 |
| GET | `/metrics` | JSON 格式运行指标 |
| GET | `/prometheus` | Prometheus exposition 格式指标 |
