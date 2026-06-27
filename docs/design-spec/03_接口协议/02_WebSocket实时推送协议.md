# WebSocket 实时推送协议

## 1. 设计目标

WebSocket 用于向前端实时推送工单处理进度。由于工单工作流在后台异步执行，前端不能只依赖 HTTP 轮询获取状态，实时推送能让用户看到每个 Agent 节点的完成情况。

## 2. 连接地址

### 2.1 单工单订阅

`WS /api/ws/tickets/{ticket_id}`

用于订阅某一个工单的处理进度，适合工单详情页使用。

### 2.2 全局监控订阅

`WS /api/ws/monitor`

用于接收所有工单的状态更新，适合 Agent 监控页或仪表盘使用。

## 3. 消息格式

```json
{
  "ticket_id": "TK-20260624-001",
  "status": "processing",
  "message": "工单处理完成",
  "timestamp": "2026-06-24T10:00:00",
  "node": "process",
  "data": {
    "category": "technical",
    "priority": "P1",
    "review_score": 0.85,
    "retry_count": 0,
    "span": {
      "span_id": "SP-20260624-001",
      "span_type": "node",
      "name": "process",
      "duration": 1.23,
      "status": "ok"
    }
  }
}
```

## 4. 字段说明

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ticket_id` | string | 工单 ID |
| `status` | string | 当前工单状态 |
| `message` | string | 给前端展示的中文消息 |
| `timestamp` | string | 推送时间 |
| `node` | string | 刚完成的工作流节点 |
| `data` | object | 节点摘要数据 |

## 5. 节点名称

| 节点 | 展示含义 |
| --- | --- |
| `receive` | 接收工单 |
| `classify` | 智能分类 |
| `route` | 路由决策 |
| `process` | 工单处理 |
| `review` | 质量审核 |
| `auto_reply` | 自动回复 |
| `escalate` | 升级处理 |
| `notify` | 发送通知 |
| `complete` | 归档完成 |
| `retry_check` | 重试检查 |
| `handle_failure` | 失败处理 |

## 6. 人工审核事件

除节点完成事件外，全局监控通道（`/api/ws/monitor`）还会广播两类人工审核事件，前端按 `type` 字段分发处理。

### 6.1 review_requested

工单转入人工审核队列时广播。触发场景：

- `escalate` 节点（投诉/P0）
- `retry_check` 达到最大重试次数（review_failed）
- 工作流异常兜底（error_fallback）
- 用户反馈不满意（user_request）

```json
{
  "type": "review_requested",
  "ticket_id": "TK-20260624-001",
  "timestamp": "2026-06-27T10:00:00",
  "trigger_type": "escalate",
  "trigger_reason": "投诉类工单",
  "priority": "P1",
  "review_id": "HR-20260627-abcd"
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `type` | string | 固定 `"review_requested"` |
| `ticket_id` | string | 工单 ID |
| `timestamp` | string | 广播时间 |
| `trigger_type` | string | 触发类型：`escalate` / `review_failed` / `error_fallback` / `user_request` |
| `trigger_reason` | string \| null | 触发原因描述 |
| `priority` | string \| null | 工单优先级（用于前端队列排序提示） |
| `review_id` | string | 审核单 ID（用于跳转审核详情） |

### 6.2 review_decided

审核员通过 `POST /api/reviews/{ticket_id}/decision` 提交决策后广播。

```json
{
  "type": "review_decided",
  "ticket_id": "TK-20260624-001",
  "timestamp": "2026-06-27T11:00:00",
  "decision": "approve",
  "reviewer_id": "reviewer-1",
  "next_node": "notify"
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `type` | string | 固定 `"review_decided"` |
| `ticket_id` | string | 工单 ID |
| `timestamp` | string | 广播时间 |
| `decision` | string | 决策：`approve` / `reject` / `rewrite` / `reprocess` |
| `reviewer_id` | string | 审核员 ID |
| `next_node` | string \| null | 工作流恢复后即将执行的下一节点（`notify` / `process` / `complete`） |

### 6.3 触发链路

- `review_requested` 由 `_run_workflow` 检测 `human_review_wait` 节点输出的 `__review_requested__` 标记后广播；`POST /api/tickets/{id}/feedback` 在不满意路径中直接广播。
- `review_decided` 由 `submit_review_decision` 端点在调用 `resume_from_human_decision` 后广播。

## 7. 断开处理

后端维护两类连接列表：

- 按 `ticket_id` 分组的单工单连接。
- 全局监控连接。

当客户端断开时，后端从连接列表中移除对应 WebSocket。发送消息失败时，也会清理断开的连接。
