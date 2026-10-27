# 项目需求规格 (PROJECT_SPEC)

> **版本**: 2.0（KB-QA-Foundation）  
> **更新**: 2026-07-29  
> **定位**: 面向企业的**可运营知识库 + 可追溯问答助手**  
> **迭代代号**: `KB-QA-Foundation` — 产品换轨、Canvas 退场、知识问答主链打通  
> **历史规格**: [PRESALE_DELIVERY_SPEC.md](./PRESALE_DELIVERY_SPEC.md)（Canvas 售前链路，已冻结，仅供遗留参考）

---

## 1. 产品背景

企业多年积累的 PPT、制度文档、产品说明、项目案例、话术与 SOP，通常散落在文件夹、个人电脑与 IM 记录中，无法系统化入库、检索与复用。

本系统目标：

```text
资料上传 → 解析入库 → 混合检索 → 对话问答（KB-first）→ 答案带引用来源
```

**不是**通用 ChatGPT，**不是** 3D 展示幕墙行业专用工具，**不是** 无限画布方案编辑器（Canvas 已隐藏冻结）。

---

## 2. 核心用户角色

| 角色 | 主要场景 | 使用频率 |
|------|----------|----------|
| 业务/销售 | 按项目提问、查案例与话术、整理客户答复 | 高 |
| 策划/方案 | 基于内部资料生成方案摘要、核对引用 | 高 |
| 项目经理 | 维护项目资料集、跟踪问答与反馈 | 中 |
| 知识运营/管理员 | 上传资料、入库、检索测试、维护案例/话术/SOP | 高 |
| 审核人员 | 评估回答质量、反馈闭环（后续增强） | 中 |

---

## 3. 产品形态

### 3.1 知识库运营后台（Admin）

路径：`/admin/*`

| 能力 | 说明 | 优先级 |
|------|------|--------|
| 资料管理 | 上传 PDF/Word/PPT，分类、入库状态 | P0 |
| 案例库 | 结构化案例，行业/场景标签 | P0 |
| 话术库 | 按场景检索的统一口径 | P1 |
| 检索测试与日志 | 验证命中、查看 retrieval_logs | P0 |
| SOP / 模板 / Prompt | 保留，供后续文档生成扩展 | P1 |
| 行业资料库 | 趋势、政策等半结构化知识 | P2 |

### 3.2 员工工作台（Workspace）

路径：`/workspace/*`

**主入口：项目知识问答**

```text
/workspace/projects          — 项目列表（按客户/商机隔离资料与对话）
/workspace/projects/new      — 轻量创建向导（基本信息 + 企业背景）
/workspace/chat/{projectId}  — 项目级问答（主界面）
```

交互原则：

1. **对话是手段，可追溯答案是目标** — 回复须尽量绑定内部来源（文档 chunk / 案例 / 话术）。
2. **KB-first** — 默认先查内部知识库，联网搜索为可配置补充。
3. **项目可选上下文** — 问答可限定在项目已绑定资料范围内。
4. **不做纯聊天** — 无引用时须明确标注「资料中未找到，需补充」或降级说明。

### 3.3 已冻结能力（本迭代隐藏，代码保留）

以下能力**退出主路径**，路由隐藏，不再作为验收项：

| 能力 | 原路径 | 状态 |
|------|--------|------|
| Canvas 无限画布 | `/workspace/canvas/*` | 重定向至 `/workspace/chat/*` |
| 视觉 Prompt / 概念图 | visual_concept Skill | 冻结 |
| 场地与屏幕参数向导 | 项目向导 Step | 已移除 |
| 策划案 10 章 / 六看 / 导出门控 | proposal 编辑器 | 冻结，后续或改为通用文档生成 |

---

## 4. 本次迭代目标（KB-QA-Foundation）

### 4.1 P0 — 必须交付

#### G1 产品入口切换

- [ ] 登录后通过项目列表 → 知识问答进入主流程
- [ ] Canvas 路由隐藏（重定向至 chat）
- [ ] 品牌与文案中性化（去除 3D/幕墙/裸眼等垂直用语）
- [ ] 项目向导精简（无 screen / 视觉步骤）

#### G2 知识库运营

- [ ] 资料上传 → 解析 → embedding 入库链路可用
- [ ] Admin 检索测试可验证 chunk 命中
- [ ] 案例库 / 话术库至少一种可被问答引用
- [ ] Demo seed 改为通用 B2B 企业资料（非 3D 专用）

#### G3 问答主链

- [ ] **KB-first**：`knowledge_search` 优先于 `web_search`
- [ ] 答案展示引用来源（文档名、章节/页码、案例标题）
- [ ] 项目级资料范围限定
- [ ] 多轮对话记忆（项目 memory / 上一轮检索）
- [ ] `WEB_SEARCH_ENABLED` 或等价配置可关闭外网搜索

#### G4 质量与交付

- [ ] `test_knowledge_qa_flow` 主链 E2E（上传 → 索引 → 提问 → 断言引用）
- [ ] `retrieval_logs` 记录 query、命中项、latency、路径（kb/web）
- [ ] 更新 `CUSTOMER_INSTALL.md` / `DEMO.md` 为知识助手演示剧本

### 4.2 P1 — 建议同期或紧接迭代

- [ ] 检索日志字段补全（structured_query、retrieved_items）
- [ ] Query 同义词扩展（`query_synonyms` 配置表）
- [ ] 元数据预过滤（industry、doc_category）
- [ ] 反馈评分与未命中问题运营看板

### 4.3 明确不做（本迭代 Out of Scope）

- GraphRAG 社区摘要 / 全局图检索
- LLM Wiki 主题页生成与浏览
- 完整 Ontology / OWL / Neo4j 工程
- 实体抽取与知识图谱入库（下一迭代 `KB-Ontology-Lite`）
- 多租户 / 细粒度 RBAC
- Canvas 能力增强或视觉生图
- Skill 市场 / ToC 工作台
- 复杂多租户、拖拽工作流、自动报价、施工图/视频

---

## 5. 架构概览

### 5.1 当前迭代架构

```text
┌──────────────── Admin ─────────────────┐
│ 资料 │ 入库 │ 案例/话术 │ 检索测试/日志 │
└──────────────────┬─────────────────────┘
                   │
┌──────────── Workspace ─────────────────┐
│  项目列表 → 知识问答（ConversationPanel）│
└──────────────────┬─────────────────────┘
                   │
      Retrieval Orchestrator（目标态）
        ├─ knowledge_search（chunk 向量 + 关键词）
        ├─ case_search / talking_points
        ├─ web_search（可选，默认开启可关闭）
        └─ Context Pack → LLM → Answer + Citations
```

### 5.2 预留扩展点（本迭代只定边界，不实现）

入库流水线预留 hook：

```text
post_chunk → entity_extract → graph_upsert → wiki_generate
```

检索路由（当前实现）：

```text
Q&A / Admin 检索测试
  → RetrievalOrchestrator
      → local   — 本地 HybridRetriever（pgvector + 关键词 + 案例）
      → fastgpt — FastGPT dataset searchTest（仅检索，不负责入库）
      → dual    — 两路合并去重
```

**FastGPT 定位**：可选的外部向量检索后端。资料上传、解析、chunk、embedding **仍走本系统 DocumentService**；仅在 `RETRIEVAL_PROVIDER=fastgpt|dual` 时，问答与检索测试走 FastGPT API。若需 FastGPT 侧也有完整副本，需单独建设同步流水线（当前迭代不包含）。

配置项：`RETRIEVAL_PROVIDER`、`FASTGPT_BASE_URL`、`FASTGPT_API_KEY`、`FASTGPT_DATASET_ID`（Admin 设置页或 `.env`）。

后续 Graph 路由预留：

```text
query_type → chunk | structured | graph | wiki
```

后续迭代路线：

| 迭代 | 代号 | 重点 |
|------|------|------|
| **当前** | `KB-QA-Foundation` | 换轨 + KB-first 问答 + Admin 运营 |
| 下一期 | `KB-Ontology-Lite` | 轻量 Ontology、实体抽取、PG 图三表 |
| 再下一期 | `KB-GraphRAG` | 子图检索、社区摘要、Global/Local 路由 |
| 再下一期 | `KB-Wiki` | LLM Wiki 主题页、审核发布 |

---

## 6. 核心原则

与 [CLAUDE.md](../CLAUDE.md) / [AGENTS.md](../AGENTS.md) 一致，本产品线强调：

1. **RAG 必须可追溯** — 禁止无法溯源的虚构内容；案例必须来自案例库。
2. **KB-first** — 内部资料优先；外网搜索受控、可关闭。
3. **缺失信息须明示** — 资料不足时标记「需进一步确认」，禁止编造报价/参数/工期。
4. **专家能力可配置** — SOP、Prompt、模板、规则走管理后台，不硬编码在代码（逐步去行业硬编码）。
5. **产物驱动** — 问答结果可沉淀为可引用片段；后续支持方案摘要导出。

---

## 7. 数据模型

> 完整字段见 [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)。以下为 KB-QA 视角下的模型说明与变更备注。

### 7.1 核心模型（活跃）

| 模型 | KB-QA 用途 |
|------|------------|
| `documents` / `document_chunks` | 非结构化知识、向量检索 |
| `cases` | 结构化案例检索与引用 |
| `talking_points` | 话术库检索 |
| `retrieval_logs` | 检索追溯与运营 |
| `conversations` / `messages` | 问答历史 |
| `projects` | 轻量上下文容器（绑定资料集 + 对话） |
| `companies` | 客户/企业基本信息 |
| `project_memories` / `conversation_states` | 跨轮记忆 |

### 7.2 保留但降级（冻结主路径）

| 模型/字段 | 说明 |
|-----------|------|
| `canvas_*` 相关表 | Canvas 冻结，不删除 |
| `projects.screen_info_json` | 废弃输入，保留列兼容旧数据 |
| `company_profiles` 六看字段 | 保留，非主链 |
| `generation_outputs`（proposal/visual） | 保留，供后续文档生成 Skill |

### 7.3 下一迭代预留（Ontology-Lite）

计划新增（设计阶段再落库）：

```text
ontology_schema   — 实体类型、关系、受控词表 JSON
entities          — 抽取或人工维护的实体
relations         — 实体间关系
chunk_entity_mentions — chunk ↔ 实体关联
topics            — LLM Wiki 主题页（KB-Wiki 迭代）
```

---

## 8. 检索规格摘要

详细规则见 [RAG_SPEC.md](./RAG_SPEC.md) 与 [RAG_IMPROVEMENT_ROADMAP.md](./RAG_IMPROVEMENT_ROADMAP.md)。

KB-QA 阶段强制要求：

```text
1. 结构化知识（案例、话术）— 精确匹配优先
2. 文档 chunks — 混合检索（向量 + 关键词）
3. 检索结果写入 retrieval_logs
4. 问答 Context Pack 须包含 used_chunks / used_cases 引用 ID
5. web_search 仅作补充，且须标注外网来源
```

---

## 9. 验收标准

### 9.1 标准 UAT 剧本

| 步骤 | 操作 | 预期 |
|------|------|------|
| 1 | Admin 上传 2–3 份企业资料并入库 | 状态为已入库 |
| 2 | 检索测试：「公司有哪些核心产品？」 | 命中正确 chunk，可追溯 |
| 3 | 创建项目，进入知识问答 | 进入 `/workspace/chat/{id}`，无 Canvas |
| 4 | 提问：「XX 产品的适用场景是什么？」 | 基于内部资料回答，有引用 |
| 5 | 追问上一轮内容 | 不失忆，可引用上下文 |
| 6 | 关闭 web_search 后重复步骤 4 | 仍可答内部资料问题 |
| 7 | 检查界面 | 无 3D/幕墙/屏幕参数/视觉生图主入口 |

### 9.2 自动化

- `test_knowledge_qa_flow` 通过
- `test_rag.py` 回归通过
- Canvas 相关测试标记 skip 或移入 `legacy/`（不阻塞 CI）

---

## 10. 配置项

| 变量 | 说明 | 默认 |
|------|------|------|
| `EMBEDDING_PROVIDER` | 嵌入模型提供商 | 生产须为真实 API |
| `WEB_SEARCH_ENABLED` | 是否允许联网补充 | `true`（私有化可 `false`） |
| `CANVAS_ENABLED` | 是否暴露 Canvas 路由 | `false`（重定向 chat） |

---

## 11. 文档索引

| 文档 | 状态 |
|------|------|
| [KB_PRIVATE_DELIVERY_SPEC.md](./KB_PRIVATE_DELIVERY_SPEC.md) | **有效** — 私有化客户案例交付 + Eval 闭环 + 后续预留 |
| [KB_CONSOLE_UI_SPEC.md](./KB_CONSOLE_UI_SPEC.md) | **有效** — KB 标准版 Admin/Workspace UI |
| [RAG_SPEC.md](./RAG_SPEC.md) | 有效，随 KB-first 迭代更新检索主链 |
| [API_SPEC.md](./API_SPEC.md) | 有效（Eval API 待按 KB_PRIVATE_DELIVERY_SPEC 增补） |
| [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) | 有效，Ontology / Eval 表待补充 |
| [PRESALE_DELIVERY_SPEC.md](./PRESALE_DELIVERY_SPEC.md) | **冻结** — Canvas 售前验收 |
| [CUSTOMER_INSTALL.md](./CUSTOMER_INSTALL.md) | **有效** — 知识助手私有化安装 + 本期交付范围 |
| [DEMO.md](./DEMO.md) | **有效** — KB UAT 剧本 |

---

## 12. MVP 验收清单（换轨后）

1. ✅ 内部用户可创建轻量项目并进入知识问答
2. ✅ 管理员可上传资料并完成入库
3. ✅ 问答默认基于内部知识库，答案带引用
4. ✅ 案例/话术可被检索并引用
5. ✅ 检索日志可追溯
6. ✅ 联网搜索可配置关闭
7. ✅ Canvas / 3D 垂直能力不阻塞、不暴露主路径
8. ✅ 评测中心 Hit@k 回归（kb-case-v1.0）
9. ⬜ GraphRAG / Wiki / Ontology（后续迭代）
10. ⬜ Review 队列 / Analytics（M4 下一期）
