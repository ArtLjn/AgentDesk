# 多Agent工单处理系统 — 导读

## 一句话概括

基于 LangGraph 状态机编排的 4 Agent 协作系统，自动完成工单分类→处理→审核全流程，支持重试、降级、知识库检索和 WebSocket 实时推送。

---

## 系统架构

```
用户提交工单
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI (api/)                                             │
│  POST /api/tickets → 后台触发 LangGraph 工作流               │
│  GET  /api/tickets → 查询工单状态                            │
│  WS   /ws/tickets/{id} → 实时推送进度                        │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  LangGraph 状态机 (workflow/graph.py)                       │
│                                                             │
│  receive → classify → route ─┬─ auto_reply (咨询类)         │
│                              ├─ escalate  (投诉/P0)         │
│                              └─ process → review            │
│                                    ↑        │               │
│                                    └─ retry (≤3次)          │
│                                             │               │
│                                notify ← approve/reject      │
│                                  │                          │
│                                complete → END               │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
   ┌────────────┐  ┌────────────┐  ┌────────────┐
   │ 4个Agent   │  │ 4个工具    │  │ Qdrant     │
   │ (agents/)  │  │ (tools/)   │  │ 向量数据库 │
   └────────────┘  └────────────┘  └────────────┘
```

---

## 目录结构速查

```
src/multi_agent_system/
├── config.py                    全局配置（Pydantic Settings）
├── models/                      数据模型
│   ├── ticket.py                工单模型 + 枚举（状态/分类/优先级）
│   └── knowledge.py             知识库文档模型
├── workflow/                    LangGraph 工作流
│   ├── state.py                 TicketState 状态字典定义
│   └── graph.py                 状态图：10个节点 + 3个条件边
├── agents/                      4个 LLM Agent
│   ├── classifier.py            分类Agent（分类+优先级+路由）
│   ├── processor.py             处理Agent（知识库检索+生成方案）
│   ├── reviewer.py              审核Agent（质量评分0-1）
│   └── coordinator.py           协调Agent（升级+失败处理+报告）
├── tools/                       4个工具
│   ├── knowledge_search.py      Qdrant + Ollama Embedding 检索
│   ├── db_query.py              内存模拟数据库（工单/用户CRUD）
│   ├── notification.py          通知发送（模拟 email/sms/webhook）
│   └── analytics.py             统计分析（分类分布/处理统计）
└── api/                         FastAPI 接口层
    ├── app.py                   应用初始化 + 生命周期管理
    └── routes.py                6个REST端点 + 1个WebSocket
```

---

## 核心流程详解

### 工单处理状态流转

```
RECEIVE → CLASSIFY → ROUTE
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
     AUTO_REPLY    ESCALATE      PROCESS
     (咨询类)      (投诉/P0)     (技术/账务)
          │             │             │
          │             │             ▼
          │             │         REVIEW
          │             │             │
          │             │      ┌──────┴──────┐
          │             │      ▼             ▼
          │             │   APPROVE       REJECT
          │             │   (≥0.7)       (<0.7)
          │             │      │             │
          │             │      │        RETRY_CHECK
          │             │      │        (≤3次→PROCESS)
          │             │      │        (>3次→FAILED)
          └─────┬───────┘      │
                ▼              │
             NOTIFY ◄──────────┘
                │
             COMPLETE
```

### 路由规则

| 分类 | 优先级 | 路径 |
|------|--------|------|
| inquiry（咨询） | 任意 | auto_reply → 直接生成回复 |
| complaint（投诉） | 任意 | escalate → 升级人工 |
| 技术问题/账务 | P0 | escalate → 升级人工 |
| 技术问题/账务 | P1-P3 | process → review → complete |

### 审核机制

- ReviewerAgent 从 4 个维度打分：准确性、可行性、完整性、专业性
- 评分 ≥ 0.7 → 通过，进入通知环节
- 评分 < 0.7 → 打回重做，重试上限 3 次
- 超过 3 次仍不通过 → 标记 FAILED

---

## 4 个 Agent 详解

### ClassifierAgent — 分类Agent

**职责**：分析工单内容，输出分类 + 优先级 + 路由建议

```python
agent = ClassifierAgent(model="deepseek-chat")
result = await agent.classify("系统报错 ERR-5001")
# → {"category": "technical", "priority": "P1", "reason": "系统错误需要技术支持"}
```

**降级策略**：LLM 调用失败时，按关键词匹配（"崩溃"→技术，"退款"→账务，"投诉"→投诉，其余→咨询）

### ProcessorAgent — 处理Agent

**职责**：先检索知识库找相关方案，再由 LLM 生成解决方案

```python
agent = ProcessorAgent(model="deepseek-chat", knowledge_tool=kb_tool)
result = await agent.process("系统报错", "technical", "P1")
# → {"result": "根据排查手册...", "references": [...]}
```

**工作流程**：`知识库检索` → `格式化上下文` → `LLM 生成方案`

### ReviewerAgent — 审核Agent

**职责**：从 4 个维度评估处理结果质量，返回 0-1 评分

```python
agent = ReviewerAgent(model="deepseek-chat")
result = await agent.review("系统报错", "建议重启服务...", "technical")
# → {"score": 0.85, "feedback": "方案准确且具体..."}
```

### CoordinatorAgent — Supervisor协调Agent

**职责**：全局协调，处理异常场景（升级/失败/报告生成）

```python
agent = CoordinatorAgent(model="deepseek-chat", notification_tool=ntf, knowledge_tool=kb)
await agent.escalate("ticket-123", "P0紧急")      # 升级工单
await agent.handle_failure("ticket-456", "超时")   # 处理失败
report = await agent.generate_report(tickets)      # 生成报告
```

---

## 4 个工具详解

### KnowledgeSearchTool — 知识库检索

- 向量数据库：Qdrant（Docker 容器）
- Embedding 模型：qwen3-embedding:4b（2560 维，本地 Ollama）
- 文档分块：512 字符/块，64 字符重叠
- 支持：批量添加文档、语义检索（top_k + score_threshold）

### DBQueryTool — 模拟数据库

- 纯内存 dict 存储，无外部依赖
- 预置 3 个测试用户（U001 张三/VIP、U002 李四、U003 王五/VIP）
- 支持：工单 CRUD、用户查询、工单历史、同分类工单

### NotificationTool — 通知发送

- 模拟实现，记录到内存列表
- 支持 3 种渠道：email / sms / webhook
- 每次发送自动记录时间戳和渠道

### AnalyticsTool — 统计分析

- 数据源：DBQueryTool（内存数据）
- 提供：分类分布、优先级分布、处理统计（总数/完成/失败/成功率）、每日趋势

---

## API 接口

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/tickets` | 提交工单，后台触发工作流，立即返回 ticket_id |
| GET | `/api/tickets/{id}` | 查询工单详情（状态/分类/结果/评分/消息链） |
| GET | `/api/tickets` | 工单列表，支持 `?status=&category=&limit=&offset=` |
| POST | `/api/knowledge` | 上传文档到 Qdrant 知识库 |
| GET | `/api/analytics` | 统计面板数据 |
| WS | `/api/ws/tickets/{id}` | WebSocket 实时推送处理进度 |

---

## 关键设计决策

| 决策 | 原因 |
|------|------|
| LangGraph 状态机 | 工单处理天然适合有向图，条件分支+重试循环用 StateGraph 表达最自然 |
| Agent 降级兜底 | 每个 Agent 都有 LLM + 占位双路径，API 不可用时系统仍能工作 |
| 模块级 Agent 注入 | `build_ticket_graph(agents=...)` 注入 Agent 到 graph 节点，不传则用占位实现 |
| 延迟初始化 OpenAI client | `property` 模式，避免构造时必须提供 API Key |
| 内存模拟数据库 | 降低部署复杂度，生产环境可替换为真实数据库 |
| 后台异步执行工作流 | `asyncio.create_task` 提交后立即返回，不阻塞 HTTP 响应 |

---

## 测试覆盖

49 个测试，覆盖三个维度：

- **test_workflow.py** (16 个)：状态流转测试，4 条路径（咨询/投诉/技术/重试）+ 条件边决策
- **test_agents.py** (20 个)：4 个 Agent 的 LLM 调用 + 降级兜底
- **test_api.py** (13 个)：API 端点 CRUD + 知识库上传 + 统计

---

## 部署

Docker Compose 编排 3 个服务：

```bash
./deploy.sh    # 一键部署到 HomeUbuntu (172.16.58.68)
```

- **Qdrant** :6333 — 向量数据库
- **FastAPI** :8000 — Agent API
- **Streamlit** :8501 — Web 前端

测试页面：`web/test.html`，浏览器打开即可测试所有 API。
