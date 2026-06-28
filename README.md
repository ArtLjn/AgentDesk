# AgentDesk — 基于多智能体协同的工单处理系统

AgentDesk 是一个基于 LangGraph 多智能体协同的企业级工单自动化处理系统。通过分类、处理、审核、协调四个 Agent 的协作，实现工单从接收到完成的全生命周期自动化管理。

## 系统架构

```
                          ┌─────────────────────────────────────────┐
                          │            FastAPI + WebSocket          │
                          └──────────────┬──────────────────────────┘
                                         │
                          ┌──────────────▼──────────────────────────┐
                          │         LangGraph 状态机编排             │
                          │  receive → classify → route → process  │
                          │  → review → notify → complete           │
                          └──────────────┬──────────────────────────┘
                                         │
              ┌──────────────┬───────────┼───────────┬──────────────┐
              │              │           │           │              │
     ┌────────▼───┐ ┌───────▼────┐ ┌───▼──────┐ ┌─▼──────────┐ ┌─▼──────────┐
     │ Classifier │ │ Processor  │ │ Reviewer │ │ Coordinator│ │   Tools    │
     │   Agent    │ │   Agent    │ │  Agent   │ │   Agent    │ │            │
     └────────────┘ └────────────┘ └──────────┘ └────────────┘ │ • DB Query │
                                                                 │ • Vector   │
                                                                 │ • Notify   │
                                                                 └────────────┘
```

```
src/multi_agent_system/
├── api/              # FastAPI REST API + WebSocket
├── agents/           # 四大 Agent（分类/处理/审核/协调）
├── core/             # 基础设施（重试/降级/缓存/指标/路由/追踪）
├── models/           # Pydantic 数据模型
├── tools/            # 外部工具（数据库/向量检索/通知）
├── workflow/         # LangGraph 状态机编排
└── config.py         # 全局配置
```

## 核心特性

- **LangGraph 工作流编排**：工单生命周期状态机（接收 → 分类 → 路由 → 处理 → 审核 → 通知）
- **四 Agent 协同**：分类 Agent（智能路由）、处理 Agent（RAG 增强）、审核 Agent（质量把关）、协调 Agent（全局调度）
- **人工审核工作台**：AI 处理不确定时挂起工单，由审核员四选一决策（通过 / 改写 / 重处理 / 驳回），CoordinatorAgent 提供辅助决策建议，全程留痕
- **智能降级机制**：LLM 调用失败时自动降级到关键词匹配/默认策略
- **RAG 稳定检索**：ProcessorAgent 会对工单预检索知识库，embedding 异常时自动改用关键词兜底检索
- **模型路由**：按任务类型（classify/process/review）自动选择不同模型
- **LLM 结果缓存**：LRU + TTL 缓存，减少重复 Token 消耗
- **Prometheus 监控**：HTTP/Agent/LLM/缓存全链路指标，Grafana 可视化
- **分布式追踪与决策链**：Span 树结构记录 Agent 执行轨迹、LLM 输入输出、工具调用、Token 用量和关键决策点
- **WebSocket 实时推送**：工单处理状态实时同步到前端
- **知识库检索**：基于 Qdrant 向量检索增强 Agent 处理能力，工单详情中的知识库参考可跳转回知识库页面核对原文

## 前端页面

前端是一个面向演示和运维的管理端，覆盖工单处理闭环的主要视图：

- **Dashboard**：展示工单总览、成功率、平均耗时、待处理风险、人工审核压力和近期工单。
- **工单管理**：支持结构化提交工单、筛选搜索、分页浏览和进入详情页。
- **工单详情**：展示工单内容、处理结果、知识库参考、Agent 消息链和执行决策链。
- **审核工作台**：人工处理待审核工单，并查看 AI 辅助建议。
- **Agent 监控**：查看 trace 列表、Span 时间线、节点输入输出、RAG 命中、Token 用量和决策点。
- **知识库**：上传文档、查看 Qdrant 文档分块、按标题/分类/内容检索，并支持从工单参考跳转定位。

## 人工审核工作台

当 Agent 自主处理不够确定时（投诉类工单、AI 审核失败 3 次、工作流异常、用户主动反馈不满意），工单会自动挂起进入人工审核队列：

- **审核入口**：侧边栏"审核工作台"，支持按触发类型 / 分类 / 优先级筛选
- **AI 辅助**：CoordinatorAgent 给出推荐决策 + 置信度 + 关注点
- **四种决策**：通过（沿用 AI 结果）/ 改写（覆盖结果）/ 重处理（清空 retry 重新跑）/ 驳回
- **WebSocket 实时推送**：新工单进入队列时即时刷新
- **指标追踪**：AI 建议采纳率（ai_adoption_rate）、平均决策时长等统计可视化

## 决策链与 RAG 追踪

系统会在关键节点写入结构化 trace，用于解释 Agent 为什么这样处理：

- **分类决策**：记录候选分类、选中分类、置信度和理由。
- **审核决策**：记录审核分数、阈值、通过或重试选择。
- **重试边界**：记录 retry 与人工升级之间的阈值判断。
- **LLM 调用**：记录模型、任务类型、消息摘要、输出内容、finish_reason 和 Token 用量。
- **知识库检索**：记录 query、top_k、命中文档、最高相似度和分块预览。

前端可通过工单详情页或 Agent 监控页查看这些信息。后端也提供独立接口：

```bash
GET /api/traces/{trace_id}/decisions
```

返回该 trace 中抽取出的所有决策点，便于前端绘制决策时间线和调试 Agent 路由。

## 技术栈

| 类别 | 技术 |
|------|------|
| LLM 接口 | OpenAI SDK（兼容 Ollama / DeepSeek 等） |
| 工作流编排 | LangGraph |
| API 框架 | FastAPI + Uvicorn |
| 前端 | React 19 + TypeScript + TailwindCSS + shadcn/ui |
| 数据校验 | Pydantic |
| 向量数据库 | Qdrant |
| 监控 | Prometheus + Grafana |
| 日志 | loguru |
| 容器化 | Docker + Docker Compose |

## 环境要求

- Python 3.10+
- Node.js 18+
- Docker + Docker Compose（可选，用于 Qdrant + Grafana + Prometheus）
- OpenAI 兼容 API Key

## 快速开始

### 本地开发

```bash
# 1. 克隆项目
git clone https://github.com/ArtLjn/ai-agent-learning
cd ai-agent-learning

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填写 LLM_BASE_URL、LLM_API_KEY 等

# 5. 启动后端
uvicorn src.multi_agent_system.api.app:app --reload

# 6. 启动前端（新终端）
cd web && npm install && npm run dev
```

### Docker 部署

```bash
# 一键部署（含 API + 前端 + Qdrant + Grafana + Prometheus）
bash scripts/deploy-docker.sh
```

服务地址：
- 前端: http://localhost:5173
- API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090

## 使用示例

### 创建工单

```bash
curl -X POST http://localhost:8000/api/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "title": "无法登录系统",
    "content": "点击登录按钮后页面报错 500",
    "customer_id": "CUST-001"
  }'
```

### WebSocket 实时监听

```javascript
const ws = new WebSocket('ws://localhost:8000/api/ws/monitor');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('工单状态更新:', data);
};
```

### 查看决策点

```bash
curl http://localhost:8000/api/traces/{trace_id}/decisions
```

### 上传知识库文档

```bash
curl -X POST http://localhost:8000/api/knowledge \
  -H "Content-Type: application/json" \
  -d '{
    "title": "账务处理指南",
    "category": "billing",
    "content": "核对扣费时应先检查订单记录、服务周期和支付流水。"
  }'
```

## 项目文档

- [项目架构导读](docs/project-guide.md) — 完整架构说明和代码阅读指南

## License

MIT
