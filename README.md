# AI Agent 开发工程师学习实战项目

本项目是 AI Agent 开发工程师学习路线的实战代码库，包含 3 个梯度级别的实战项目：

1. **基础 Agent 实现**（`src/basic_agents/`）：ReAct、Plan-Execute、Reflexion 等基础模式
2. **RAG 系统开发**（`src/rag_systems/`）：个人知识库、论文阅读助手
3. **企业级多 Agent 自动化系统**（`src/multi_agent_system/`）：基于 LangGraph 的工单处理系统

---

## 项目架构

```
src/multi_agent_system/
├── api/              # FastAPI REST API + WebSocket
├── agents/           # 四大 Agent（分类/处理/审核/协调）
├── core/             # 基础设施（重试/降级/缓存/指标/路由）
├── models/           # Pydantic 数据模型
├── tools/            # 外部工具（数据库/向量检索/通知）
├── workflow/         # LangGraph 状态机编排
└── config.py         # 全局配置
```

详细架构说明见 [docs/project-guide.md](docs/project-guide.md)。

---

## 核心特性

- **LangGraph 工作流编排**：工单生命周期状态机（接收 → 分类 → 路由 → 处理 → 审核 → 通知）
- **智能降级机制**：LLM 调用失败时自动降级到关键词匹配/默认策略
- **模型路由**：按任务类型（classify/process/review）自动选择不同模型
- **LLM 结果缓存**：LRU + TTL 缓存，减少重复 Token 消耗
- **Prometheus 监控**：HTTP/Agent/LLM/缓存全链路指标，Grafana 可视化
- **WebSocket 实时推送**：工单处理状态实时同步到前端

---

## 环境要求

- Python 3.10+
- Docker + Docker Compose（可选，用于 Qdrant + Grafana + Prometheus）
- OpenAI 兼容 API Key（支持 Ollama Cloud、DeepSeek 等）

---

## 快速开始

### 本地开发

```bash
# 1. 克隆项目
git clone <repo-url>
cd ai-agent-learning

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填写 LLM_BASE_URL、LLM_API_KEY 等

# 5. 启动服务
uvicorn src.multi_agent_system.api.app:app --reload
```

### Docker 部署

```bash
# 一键部署（含 API + Qdrant + Grafana + Prometheus）
bash deploy.sh
```

服务地址：
- API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090

---

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
const ws = new WebSocket('ws://localhost:8000/api/ws');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('工单状态更新:', data);
};
```

---

## 项目文档

- [项目架构导读](docs/project-guide.md) — 完整架构说明和代码阅读指南

---

## 技术栈

| 类别 | 技术 |
|------|------|
| LLM 接口 | OpenAI SDK |
| 工作流编排 | LangGraph |
| API 框架 | FastAPI + Uvicorn |
| 数据校验 | Pydantic |
| 向量数据库 | Qdrant |
| 缓存 | cachetools |
| 监控 | Prometheus + Grafana |
| 日志 | loguru |
| 容器化 | Docker + Docker Compose |
