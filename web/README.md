# AgentDesk Web

AgentDesk Web 是智能工单处理系统的 React 管理端，负责展示工单处理、人工审核、知识库管理和 Agent 执行追踪。

## 功能页面

- **Dashboard**：查看工单量、成功率、平均耗时、风险工单、人工审核压力和近期动态。
- **工单管理**：结构化提交工单，支持问题类型、紧急程度、影响范围、联系方式等字段。
- **工单详情**：展示工单内容、处理结果、知识库参考、Agent 消息链、Trace 时间线和决策点明细。
- **审核工作台**：处理待人工审核工单，查看 AI 建议并执行通过、改写、重处理或驳回。
- **Agent 监控**：查看 trace 列表、Span 树、节点输入输出、RAG 命中、Token 用量和决策记录。
- **知识库**：上传知识文档，查看文档分块，按标题、分类或正文检索；支持从工单参考跳转定位。
- **系统设置**：查看运行时配置和服务状态。

## 技术栈

- React 19
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui
- TanStack Query
- lucide-react
- react-markdown + remark-gfm

## 本地开发

```bash
npm install
npm run dev
```

默认开发地址为 `http://localhost:5173`。前端 API 基址为 `/api`，本地开发时由 Vite 代理到后端服务。

## 常用脚本

```bash
npm run dev      # 启动开发服务
npm run build    # 类型检查并构建生产包
npm run lint     # 运行 ESLint
npm run preview  # 预览生产构建
```

## 验证

知识库参考跳转的纯函数测试可用 Node 内置测试运行：

```bash
node --experimental-strip-types --test tests/knowledgeReference.test.ts
```

生产构建验证：

```bash
npm run build
```
