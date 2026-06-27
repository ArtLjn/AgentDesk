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
| `review_score` | number/null | 审核评分 |
| `retry_count` | number | 重试次数 |
| `status` | string | 当前状态 |
| `messages` | list | 节点消息链 |
| `error` | string/null | 错误信息 |
| `user_context` | object | 用户上下文，可选 |
| `__trace_id__` | string/null | 执行追踪 ID |

## 2. ClassifierAgent 输出

```json
{
  "category": "technical",
  "priority": "P1",
  "reason": "用户反馈系统报错，影响登录"
}
```

约束：

- `category` 必须属于 `technical`、`billing`、`complaint`、`inquiry`。
- `priority` 必须属于 `P0`、`P1`、`P2`、`P3`。
- `reason` 应简短说明分类依据。

## 3. ProcessorAgent 输出

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

## 4. ReviewerAgent 输出

```json
{
  "score": 0.86,
  "feedback": "方案覆盖了账号状态和服务端日志检查，具备可执行性。"
}
```

约束：

- `score` 范围为 0 到 1。
- `feedback` 应说明通过或不通过的原因。

## 5. CoordinatorAgent 输出

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

## 6. 消息链约定

每个节点可向 `messages` 追加一条记录：

```json
{
  "role": "classifier",
  "content": "分类结果: technical, 优先级: P1"
}
```

消息链主要用于调试、追踪和详情展示，不作为强一致业务数据。

