# 企业知识助手 — 私有化验收演示脚本

> 适用：KB 标准版（`KB_SKU=standard`）客户现场 / 内部 UAT  
> 预计时长：**20–30 分钟**  
> 规格依据：[PROJECT_SPEC.md](./PROJECT_SPEC.md) §9.1、[KB_PRIVATE_DELIVERY_SPEC.md](./KB_PRIVATE_DELIVERY_SPEC.md)

## 演示前准备

| 项 | 说明 |
|----|------|
| 访问地址 | 前端 `http://<主机>:3000` |
| 管理员 | `.env` 中 `INITIAL_ADMIN_EMAIL` / `INITIAL_ADMIN_PASSWORD`（生产勿用 demo123） |
| 演示资料 | 准备 2–3 份企业 PDF/Word/TXT（产品说明、制度、FAQ 等） |
| AI | 验收问答质量建议接真实 LLM + Embedding；流程验收可用 `LLM_PROVIDER=mock` |
| 环境变量 | `NEXT_PUBLIC_KB_SKU=standard`（默认）；`SEED_DEMO_CONTENT=false`（生产） |

## 标准 UAT 步骤

| 步 | 操作 | 预期 |
|----|------|------|
| 1 | `/admin/assets` 上传 2–3 份资料，执行**入库/索引** | 文档状态为已入库，chunk 可见 |
| 2 | `/admin/rag-test` 提问并查看 **Context Pack 预览** | 命中片段 + 预览与问答注入格式一致 |
| 3 | 在 Lab 选择评测集，对正确命中点 **存为用例** | 评测中心出现对应用例 |
| 4 | `/admin/eval` → **导入交付冒烟模板** 或 Run 已有集 | Run 完成，Hit@k / 通过数可见 |
| 5 | `/workspace/projects/new` 创建轻量项目 | 进入知识问答（`/workspace/chat/{id}`），无 Canvas 主路径 |
| 6 | 提问与资料相关的问题（如产品适用场景） | 回答基于内部资料，界面或元数据有**引用** |
| 7 | 追问上一轮内容 | 多轮连贯，仍可走知识库 |
| 8 | `/admin/retrieval-logs` 查看最近日志 | 存在对应 query，可关联 conversation / message（问答后） |
| 9 | （可选）`/admin/settings` 关闭 web_search 后重复步骤 6 | 仍可回答纯内部资料问题 |
| 10 | 浏览工作台侧栏 | 无 3D 幕墙 / 视觉生图 / Canvas 方案主入口（standard SKU） |

## 检索实验室 → 评测闭环（讲解要点）

1. Lab 与项目问答使用**同一检索编排**（非独立测试接口）。  
2. 用例支持 **expected_keywords** 或 Lab 保存的 **expected_chunk_ids**。  
3. Eval Run 写入 `retrieval_logs`，`triggered_by=eval_replay`，便于与线上对比。

## Mock 模式说明

`LLM_PROVIDER=mock` 时：

- 上传、检索、Eval Run、日志追溯可完整验证  
- 问答文案为 Mock，**不代表最终生成质量**  
- 向客户说明：「流程与可追溯性是交付核心；接真实模型后答案质量取决于资料与模型」

## 真实 LLM 配置（签单前推荐）

```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=sk-...
```

重启 API 后重复步骤 5–8，目检引用与答案是否 grounded。

## 常见问题

| 现象 | 处理 |
|------|------|
| 检索无命中 | 确认资料已索引；问句与文档用语接近 |
| Eval Hit@k 为 0 | 编辑用例 expected_keywords 或从 Lab 重新保存 chunk |
| 401 | 先登录 `/login` |
| 问答无引用 | 确认 forceIntent 为 conversational；项目下是否有已索引资料 |

## 自动化回归

```bash
cd apps/api && pytest app/tests/test_knowledge_qa_flow.py app/tests/test_eval_run.py app/tests/test_kb_m1.py -q
```
