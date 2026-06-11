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
- **智能降级机制**：LLM 调用失败时自动降级到关键词匹配/默认策略
- **模型路由**：按任务类型（classify/process/review）自动选择不同模型
- **LLM 结果缓存**：LRU + TTL 缓存，减少重复 Token 消耗
- **Prometheus 监控**：HTTP/Agent/LLM/缓存全链路指标，Grafana 可视化
- **分布式追踪**：Span 树结构，记录每个 Agent 的执行轨迹与耗时
- **WebSocket 实时推送**：工单处理状态实时同步到前端
- **知识库检索**：基于 Qdrant 向量检索增强 Agent 处理能力

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

## 项目文档

- [项目架构导读](docs/project-guide.md) — 完整架构说明和代码阅读指南

## License

MIT
