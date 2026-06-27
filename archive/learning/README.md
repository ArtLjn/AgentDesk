# 学习产物归档

本目录保存项目早期 AI Agent 学习阶段的代码和测试，包括 ReAct、Plan-Execute、Plan-ReAct、Reflection、文档处理工作流、论文阅读助手等示例。

这些内容不属于当前毕业设计“基于多智能体协同的智能工单处理系统设计与实现”的主业务代码，因此从 `src/basic_agents` 移出，归档到这里保留参考价值。

## 目录说明

| 目录 | 内容 |
| --- | --- |
| `basic_agents/` | 基础 Agent 示例实现 |
| `examples/` | 早期命令行示例 |
| `rag_systems/` | 早期 RAG 与论文阅读学习模块 |
| `web_legacy/` | 旧版静态测试页面 |
| `tests/basic_agents/` | 基础 Agent 的历史测试 |
| `tests/rag_systems/` | RAG 学习模块的历史测试 |

## 使用说明

归档代码仍保留 Python 包结构，导入路径使用 `archive.learning.*`。如果需要单独运行历史测试，可指定该目录下的测试文件。

当前毕业设计主线请优先查看：

- `src/multi_agent_system/`
- `web/`
- `docs/design-spec/`
