# Agent 内部数据契约

## 1. TicketState

`TicketState` 是 LangGraph 工作流中的共享状态。各节点通过读取和更新该状态完成协作。

核心字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ticket_id` | string | 工单 ID |
| `content` | string | 原始工单内容 |
| `category` | string/null | 分类结果 |
| `priority` | string/null | 优先级 |
| `processing_result` | string/null | 处理结果 |
| `references` | list | 知识库引用列表 |
| `review_score` | number/null | 审核评分 |
| `retry_count` | number | 重试次数 |
| `status` | string | 当前状态 |
| `messages` | list | 节点消息链 |
| `error` | string/null | 错误信息 |
| `user_context` | object | 用户上下文，可选 |
| `__trace_id__` | string/null | 执行追踪 ID |
| `trigger_type` | string/null | 人工审核触发类型 |
| `trigger_reason` | string/null | 人工审核触发原因 |
| `__human_decision__` | object/null | 人工审核恢复时注入的决策信息 |
| `conversation_context` | string/null | 用户补充信息与审核员沟通上下文 |

## 2. TicketIntentAgent 输出

```json
{
  "title": "后台 504 无法登录",
  "category": "technical",
  "priority": "P1",
  "impact": "部分用户受影响",
  "expectation": "请尽快定位并恢复服务",
  "contact": "ops@example.com",
  "occurred_at": "今天 上午 10:15",
  "intent_kind": "incident",
  "requires_business_operation": false,
  "required_fields": [],
  "can_auto_resolve": true,
  "risk_level": "medium",
  "requires_human_review": false,
  "risk_reason": "",
  "confidence": 0.86,
  "reason": "描述包含 504 和无法登录",
  "content": "【问题标题】后台 504 无法登录\n【问题类型】技术支持\n..."
}
```

约束：

- `category` 和 `priority` 必须落在系统枚举范围内。
- `content` 是后续 LangGraph 工作流消费的格式化正文。
- `requires_business_operation=true` 且 `required_fields` 非空时，后续路由更倾向进入人工审核，由审核员判断是否请求用户补充。
- LLM 不可用时允许使用本地规则兜底。

## 3. ClassifierAgent 输出

```json
{
  "category": "technical",
  "priority": "P1",
  "intent_kind": "incident",
  "requires_business_operation": false,
  "required_fields": [],
  "can_auto_resolve": true,
  "risk_level": "medium",
  "requires_human_review": false,
  "risk_reason": "",
  "confidence": 0.9,
  "reason": "用户反馈系统报错，影响登录"
}
```

约束：

- `category` 必须属于 `technical`、`billing`、`complaint`、`inquiry`。
- `priority` 必须属于 `P0`、`P1`、`P2`、`P3`。
- `required_fields` 用于表达业务操作缺失字段，例如 `order_id`、`payment_record`、`user_id`。
- `reason` 应简短说明分类依据。

## 4. ReActProcessorAgent 输出

```json
{
  "result": "建议先检查账号状态，再查看服务端登录接口日志。",
  "references": [
    {
      "title": "登录失败处理手册",
      "score": 0.82
    }
  ]
}
```

约束：

- `result` 不能为空。
- `references` 可以为空数组。
- 如果知识库不可用，允许只返回 `result`。

## 5. ReviewerAgent 输出

```json
{
  "score": 0.86,
  "feedback": "方案覆盖了账号状态和服务端日志检查，具备可执行性。"
}
```

约束：

- `score` 范围为 0 到 1。
- `feedback` 应说明通过或不通过的原因。

## 6. CoordinatorAgent 输出

升级处理示例：

```json
{
  "status": "escalated",
  "reason": "投诉类工单需要人工介入",
  "assignee": "manual_support"
}
```

失败处理示例：

```json
{
  "status": "failed",
  "reason": "连续多次审核未通过",
  "suggestion": "建议人工复核"
}
```

人工审核辅助决策示例：

```json
{
  "recommended_decision": "request_info",
  "confidence": 0.72,
  "reasoning": "工单涉及退款核查，但缺少订单号和支付流水号",
  "key_concerns": ["缺少 order_id", "缺少 payment_record"]
}
```

## 7. 人工审核决策输入

```json
{
  "decision": "request_info",
  "decision_reason": "请补充订单号和支付流水号",
  "rewritten_result": "请先确认账号状态，再检查登录接口日志和 504 时间段网关日志。",
  "reviewer_id": "reviewer-001"
}
```

约束：

- `decision` 只能是 `approve`、`reject`、`rewrite`、`reprocess`、`request_info`。
- `decision_reason` 必填且不能为空白。
- `decision=rewrite` 时 `rewritten_result` 必填。
- `decision=request_info` 时不需要 `rewritten_result`，`decision_reason` 会作为用户可见的补充说明写入 `ticket_messages`。

## 8. 消息链约定

每个节点可向 `messages` 追加一条记录：

```json
{
  "role": "classifier",
  "content": "分类结果: technical, 优先级: P1"
}
```

消息链主要用于调试、追踪和详情展示，不作为强一致业务数据。

## 9. 用户补充沟通记录

`ticket_messages` 是可持久化的业务沟通记录，用于保存审核员补充请求和用户回复。

创建用户消息请求：

```json
{
  "content": "订单号是 202606290001，支付流水号是 PAY123456",
  "sender_id": "user-001"
}
```

查询返回结构：

```json
{
  "message_id": "TM-20260629-001",
  "ticket_id": "TK-20260629-001",
  "sender_type": "user",
  "sender_id": "user-001",
  "content": "订单号是 202606290001，支付流水号是 PAY123456",
  "metadata": {"source": "user_input"},
  "created_at": "2026-06-29T10:35:00"
}
```

恢复工作流时，系统读取最近 20 条消息并拼接为：

```text
[reviewer] 请补充订单号和支付流水号
[user] 订单号是 202606290001，支付流水号是 PAY123456
```

该文本写入 `TicketState.conversation_context`，`process` 节点会把它追加到处理 Agent 输入中，要求 Agent 结合原始工单和补充信息处理。
