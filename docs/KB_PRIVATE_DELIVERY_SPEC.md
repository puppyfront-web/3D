# 私有化知识库交付规格 (KB_PRIVATE_DELIVERY_SPEC)

> **版本**: 1.1  
> **更新**: 2026-08-07  
> **迭代代号**: `KB-Case-Delivery` — 可交付客户案例 + 检索评估闭环  
> **上位文档**: [PROJECT_SPEC.md](./PROJECT_SPEC.md)（KB-QA-Foundation 产品换轨）  
> **关联**: [RAG_SPEC.md](./RAG_SPEC.md)、[DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)、[API_SPEC.md](./API_SPEC.md)、[KB_CONSOLE_UI_SPEC.md](./KB_CONSOLE_UI_SPEC.md)

---

## 1. 文档目的

本规格定义：

1. **私有化单实例**交付形态下，产品做到「**客户案例级**」所需的功能、架构与验收标准。  
2. **检索评估测**（Retrieval Lab + Eval Center + 日志追溯）的设计与实现边界。  
3. **本期不做**但需在架构与数据模型上**预留扩展点**的能力（多租户、Skill 市场、GraphRAG 等）。

实施、研发、测试以本规格 + PROJECT_SPEC 为准；Canvas/售前主链以 [PRESALE_DELIVERY_SPEC.md](./PRESALE_DELIVERY_SPEC.md) 为冻结参考，不纳入本期验收。

---

## 2. 产品定义

### 2.1 交付形态

```text
一条产品主线（Git tag / 镜像 digest）
    → 每客户独立部署（Docker Compose / 等价）
    → 独立 PostgreSQL + pgvector + storage
    → 独立 .env 与 Admin 配置
```

**刻意不做（本期）**：多租户 SaaS、自助注册、跨客户数据隔离的 `tenant_id` 模型。见 [§12 后续迭代与预留](#12-后续迭代与预留)。

### 2.2 客户案例级验收口径

对外可复现讲述并完成签字：

| 维度 | 标准 |
|------|------|
| 安装 | 脚本 + `.env`，30～60 分钟可用（含真实 LLM/Embedding） |
| 建库 | 上传多份资料，入库状态可见，失败可重试 |
| 验证 | Admin 命中测试 + **黄金集 Eval Run 报告**（Hit@k 等） |
| 使用 | 项目知识问答，答案带引用，多轮可用 |
| 追溯 | 问答消息可关联 `retrieval_log` 与 chunk/case |
| 安全 | 生产无默认弱口令；系统设置仅 admin |
| 叙事 | 主路径为 KB，无 Canvas/3D 主入口 |

### 2.3 知识范围模型（本期默认）

```text
全局知识库：project_id 为空的 documents + 全局 cases / talking_points
项目工作区：绑定 project_id 的 documents + 对话 + project_memories
问答检索默认：global ∪ project（并集）；Admin 可配置为 project-only（见 §6.2）
```

**预留**：按项目强制隔离策略、部门级库，见 §12.1。

---

## 3. 架构原则

### 3.1 检索统一契约（Retrieval Contract）

Admin 命中测试、项目问答、Eval 批量回放**必须**调用同一 `RetrievalOrchestrator` 及同一 Context Pack 组装规则（`knowledge_context_service`）。

概念模型：

```text
RetrievalRequest
  query: string
  project_id?: uuid
  scope: "union" | "global_only" | "project_only"   # 默认 union
  top_k: int
  filters?: { industry?, doc_category?, tags? }      # P1 逐步落地
  retrieval_provider: local | fastgpt | dual         # 与 settings 一致
  triggered_by: rag_hit_test | knowledge_qa | eval_replay | ...
  conversation_id?, message_id?                       # 线上问答
  eval_run_id?                                       # 批量评测

RetrievalResponse
  retrieved_items: [{ source, chunk_id|case_id, score, ... }]
  selected_context: object                            # 实际进 LLM 的子集
  structured_query: object
  latency_ms, path
  log_id: uuid                                        # retrieval_logs.id
```

每次检索**必须**写入 `retrieval_logs`，并尽量写满 PRD 字段（`structured_query_json`、`retrieved_items_json`、`selected_context_json`）。

### 3.2 评估闭环

```text
Retrieval Lab（单条）→ 保存 eval_case → Eval Run（批量）→ 报告 / Replay
        ↑                                                      ↓
   资料/同义词/Profile 变更 ←── Review 队列 ←── 线上问答 + 反馈
```

### 3.3 模块划分

```text
Knowledge Console（Admin）
├─ Library        资料 / 案例 / 话术 / 入库任务（M3）
├─ Retrieval Lab  命中测试 + Context 预览（M2）
├─ Eval Center    黄金集 / 批量 Run / 对比（M2）
├─ Analytics      零命中 / latency / eval 趋势（M4，简版）
├─ Review         失败问答队列（M4）
├─ Optimize       同义词 / retrieval profile（M4）
└─ System         LLM / Embedding / 检索后端 / 用户（M1 鉴权）

Workspace
└─ 项目列表 → 知识问答（/workspace/chat/{projectId}）
```

### 3.4 与外部框架关系

| 组件 | 本期 | 说明 |
|------|------|------|
| LlamaIndex | 不引入为核心栈 | 可选：内部试验 rerank/rewrite，经 adapter 接入 Orchestrator |
| LangSmith | 不对客户交付 | 研发可选；产品 Eval 在实例内 Admin |
| FastGPT | 可选检索后端 | 入库仍走本系统 DocumentService；见 PROJECT_SPEC §5.2 |

---

## 4. 本期实施范围（按里程碑）

### 4.1 M1 — 可安装、可验收（P0）

| ID | 功能 | 需求要点 | 验收 |
|----|------|----------|------|
| M1-1 | 生产 Seed | `INITIAL_ADMIN_EMAIL` / `INITIAL_ADMIN_PASSWORD`；`SEED_DEMO_CONTENT` 默认 `false`；生产不创建 demo 用户 | 新部署无 demo123 |
| M1-2 | Admin API 鉴权 | `settings` PUT、文档批量删除、模板/SOP 写操作等 `require_admin` | 非 admin 403 |
| M1-3 | KB SKU 路由 | Canvas/视觉/策划主入口隐藏或重定向；Admin 菜单收束为 KB 标准版 | UAT 无 Canvas 主路径 |
| M1-4 | 项目向导 | 仅轻量步骤；去除 3D/屏幕主文案；提交进入 chat | PROJECT_SPEC G1 |
| M1-5 | 品牌中性化 | 登录、deploy、`.env.example` 与企业知识助手一致 | 文档走查 |
| M1-6 | 检索契约 | QA 与 rag-test 同 Orchestrator；log 字段写满 | 对比 triggered_by 两路径结果一致 |
| M1-7 | 问答↔日志 | `messages.metadata` 含 `retrieval_log_id`；日志页可关联 conversation/message | 点选可追溯 |
| M1-8 | E2E | `test_knowledge_qa_flow`：上传→索引→提问→引用合法 | CI 通过 |
| M1-9 | 交付文档 | CUSTOMER_INSTALL / DEMO 对齐 KB UAT（PROJECT_SPEC §9） | 实施签字剧本 |

**环境变量（M1 新增）**：

| 变量 | 说明 | 默认 |
|------|------|------|
| `INITIAL_ADMIN_EMAIL` | 首次 seed 管理员邮箱 | 空则沿用开发默认（仅 APP_ENV≠production） |
| `INITIAL_ADMIN_PASSWORD` | 首次 seed 管理员密码 | 空则强制安装文档要求设置 |
| `SEED_DEMO_CONTENT` | 是否写入 demo 案例/SOP 种子 | `false`（production） |
| `KB_SKU` | `standard` \| `full`（full 暴露冻结模块） | `standard` |

### 4.2 M2 — 可验证（P0/P1，案例差异化）

| ID | 功能 | 需求要点 | 验收 |
|----|------|----------|------|
| M2-1 | Retrieval Lab | project_id、scope、top_k、provider；展示 hits + **Context Pack 预览** | 与 QA 同链路 |
| M2-2 | Eval 模型 | `eval_sets`、`eval_cases`、`eval_runs` 表 | 迁移可回滚 |
| M2-3 | Eval Run 引擎 | 逐 case 调 Orchestrator；计算 metrics | API + 单测 |
| M2-4 | Eval Center UI | 管理集/用例；执行 Run；展示失败明细 | 运营可操作 |
| M2-5 | Lab→用例 | 单条测试保存为 eval_case | 一键入库 |
| M2-6 | 冒烟集模板 | 可导入通用 B2B eval_set 模板（JSON） | Pack 文档 |

**Eval 判据（默认）**：

```text
pass = Hit@k(expected_chunk_ids) OR DocHit@k(expected_document_ids)
若配置 expected_keywords，则要求 top-k 合并正文包含全部关键词
```

**metrics_json（最小）**：

```json
{
  "total": 10,
  "passed": 8,
  "hit_at_k_rate": 0.8,
  "empty_rate": 0.0,
  "latency_ms_p50": 120,
  "latency_ms_p95": 450
}
```

**交付签字建议**：客户确认 eval_set ≥ N 条；最新 run 的 `hit_at_k_rate` ≥ 阈值（实施可配置，默认 0.8）；`empty_rate === 0`。

### 4.3 M3 — 快速介入（P1）

| ID | 功能 | 需求要点 |
|----|------|----------|
| M3-1 | Knowledge Pack | ZIP/JSON：documents 元数据 + cases + talking_points + 可选 eval_set |
| M3-2 | 入库任务 | 解析/embedding 进度、失败原因、单文档重试 |
| M3-3 | Chunk 预览 | 单文档切块列表（页码、section_title） |
| M3-4 | Admin 首次引导 | 配置模型 → 上传 → Lab 测 1 条 → 创建项目 |

### 4.4 M4 — 可运营（P1/P2，第二客户前建议完成）

| ID | 功能 | 需求要点 |
|----|------|----------|
| M4-1 | Review 队列 | 零命中、低分、引用异常自动或规则入队 |
| M4-2 | 失败入集 | 队列条目一键加入 eval_set |
| M4-3 | query_synonyms | 表 + Admin CRUD；检索前 query 扩展 |
| M4-4 | retrieval_profiles | hybrid 权重、top_k 等；eval_run config_snapshot 含 profile_version |
| M4-5 | Analytics 简版 | 7 日零命中 Top、eval_run 趋势、latency |
| M4-6 | 用户反馈 | 问答页提交问题类型 → Review |

### 4.5 M5 — 案例包装（与 M2 并行）

| ID | 交付物 |
|----|--------|
| M5-1 | 脱敏 Reference Pack + 黄金集 + 截图脚本 |
| M5-2 | 版本 tag + CHANGELOG |
| M5-3 | 备份/恢复与升级 runbook（含升级后 eval_run） |

---

## 5. 数据模型（本期新增与扩展）

> 完整列定义在实现时同步更新 [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) 与 Alembic 迁移。

### 5.1 eval_sets

| 列 | 类型 | 说明 |
|----|------|------|
| id | UUID PK | |
| name | string | |
| description | text | |
| project_id | UUID FK nullable | null = 全库评测集 |
| status | string | active / archived |
| created_at, updated_at | timestamptz | |

### 5.2 eval_cases

| 列 | 类型 | 说明 |
|----|------|------|
| id | UUID PK | |
| set_id | UUID FK | |
| query | text | |
| expected_chunk_ids | JSON array | 可选 |
| expected_document_ids | JSON array | 可选 |
| expected_keywords | JSON array | 可选 |
| must_not_keywords | JSON array | 可选 |
| notes | text | |
| source | string | hit_test / manual / production |
| created_at, updated_at | timestamptz | |

### 5.3 eval_runs

| 列 | 类型 | 说明 |
|----|------|------|
| id | UUID PK | |
| set_id | UUID FK | |
| status | string | running / completed / failed |
| config_snapshot_json | JSON | top_k, provider, profile, synonym_version |
| metrics_json | JSON | §4.2 |
| per_case_results_json | JSON | [{ case_id, pass, top_k_ids, latency_ms }] |
| created_at, completed_at | timestamptz | |

### 5.4 retrieval_logs（扩展）

| 列 | 类型 | 说明 |
|----|------|------|
| project_id | UUID nullable | **新增**，便于分析 |
| conversation_id | UUID nullable | **新增** |
| message_id | UUID nullable | **新增** |
| eval_run_id | UUID nullable | **新增** |

### 5.5 M4 预留表（本期可只建空表或 JSON 配置）

| 表 | 用途 |
|----|------|
| query_synonyms | term → expansions[] |
| retrieval_profiles | name, weights_json, status |
| review_items | message_id, reason, status, assignee |

---

## 6. API 规格摘要（Eval 模块）

Base: `/api/v1`，JWT，响应包装见 [API_SPEC.md](./API_SPEC.md)。

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET/POST | `/eval/sets` | admin | 列表/创建 |
| GET/PATCH/DELETE | `/eval/sets/{id}` | admin | |
| GET/POST | `/eval/sets/{id}/cases` | admin | |
| PATCH/DELETE | `/eval/cases/{id}` | admin | |
| POST | `/eval/runs` | admin | body: `{ set_id, config_overrides? }` |
| GET | `/eval/runs/{id}` | admin | 含 metrics 与 per_case |
| GET | `/eval/runs` | admin | 分页，按 set_id 过滤 |
| POST | `/eval/import-template` | admin | 冒烟集模板 |
| GET | `/rag/search` | 已有 | 扩展 query：project_id, scope |
| GET | `/retrieval-logs` | admin | 扩展 filter：message_id, conversation_id |

实现细节（request/response schema）在编码阶段写入 API_SPEC 第 N 章。

---

## 7. 前端页面

| 路径 | 里程碑 | 说明 |
|------|--------|------|
| `/admin/rag-test` | M2 | 升级为 Retrieval Lab（或 Tab） |
| `/admin/eval` | M2 | Eval Center |
| `/admin/retrieval-logs` | M1/M2 | 详情含 message 链接 |
| `/admin/assets` | M3 | 入库任务 + chunk 预览 |
| `/admin/review` | M4 | Review 队列 |
| `/admin/analytics` | M4 | 简版指标 |
| `/workspace/chat/[projectId]` | M1/M4 | 反馈按钮 |

UI 视觉遵循 [UI_SPEC.md](./UI_SPEC.md)；KB 标准版 Admin 侧栏以 Library / Lab / Eval / Logs / System 为主。

---

## 8. 权限模型（单实例）

| 角色 | 能力 |
|------|------|
| admin | 全库运营、Eval、System settings、用户注册 |
| user | 建项目、问答、只读 Admin 资料（可选，默认允许看 cases） |
| viewer | 只读项目与问答（P2，可选实现） |

**预留** §12.1：组织/部门级 RBAC。

---

## 9. 测试计划摘要

| 测试 | 里程碑 | 说明 |
|------|--------|------|
| `test_knowledge_qa_flow` | M1 | E2E 主链 |
| `test_eval_run_hit_at_k` | M2 | Eval 引擎 |
| `test_rag.py` | 回归 | 混合检索 |
| `test_retrieval_log_message_link` | M1 | metadata 关联 |
| UAT 剧本 | M1 | PROJECT_SPEC §9 + DEMO 更新 |

详见 [TEST_PLAN.md](./TEST_PLAN.md)（实现时增补 Eval 章节）。

---

## 10. 配置项汇总

| 变量 / setting key | 说明 |
|--------------------|------|
| `SEED_DEMO_CONTENT` | §4.1 |
| `KB_SKU` | standard / full |
| `RETRIEVAL_PROVIDER` | local / fastgpt / dual |
| `WEB_SEARCH_ENABLED` | 私有化建议 false |
| `CANVAS_ENABLED` | false |
| `qa_retrieval_scope` | app_settings：union / project_only（预留 global_only） |

---

## 11. 本期明确 Out of Scope

以下**不进入本期开发与验收**，但必须遵循 §12 预留，避免实现上堵死未来：

- 多租户 SaaS、自助注册、计费  
- Skill 市场、ToC 公开工作台  
- 完整 GraphRAG / LLM Wiki / 重型 Ontology  
- 对客户交付 LangSmith/Langfuse 账号作为运维界面  
- 完整 BI / 自定义报表平台  
- Canvas/策划/视觉作为主产品路径  

---

## 12. 后续迭代与预留

### 12.1 多租户与组织（Tenant / Org）— 未做，须预留

**未来目标**：单部署多组织（仅当产品形态从「一客户一实例」扩展为 SaaS 时）。

**预留规则**：

- 新增业务表时，评估是否需 nullable `organization_id`；本期可不填、不启用 RLS。  
- `users` 未来可增加 `organization_id`；API 层依赖注入从「当前用户」扩展为「当前 org」。  
- 文件存储路径规范：`storage/{org_id}/...`（本期可固定 `default`）。  
- **禁止**：把客户 A 的 API Key 写进共享配置表且无 scope 字段。

### 12.2 Skill 市场与 ToC 工作台 — 未做，须预留

**未来目标**：公开 Skill 卡片、插件、模板市场（CLAUDE.md 第三阶段）。

**预留规则**：

- 保持 `skills` / `skill_executions` 表与 Skill Manifest 规范；`visibility`: internal / public 已存在。  
- 新增 Skill 仅通过 `pkgutil` 注册 + Manifest，不硬编码路由。  
- 前端预留 `/portal/*` 路由命名空间（可不实现页面）。  
- `projects.external_token`、`approved_for_external` 用于对外只读方案（与 KB 问答门户可复用）。

### 12.3 GraphRAG / Ontology-Lite / Wiki — 未做，须预留

**未来目标**：见 PROJECT_SPEC 迭代表 `KB-Ontology-Lite` → `KB-GraphRAG` → `KB-Wiki`。

**预留规则**：

- 入库流水线预留 hook：`post_chunk → entity_extract → graph_upsert`（文档化，本期不调用）。  
- `RetrievalRequest` 预留 `query_route: chunk | structured | graph | wiki`。  
- `retrieval_logs.structured_query_json` 保留扩展键 `route`, `graph_hop`。  
- DATABASE_SCHEMA 预留表名：`ontology_schema`, `entities`, `relations`, `chunk_entity_mentions`, `topics`（见 PROJECT_SPEC §7.3）。

### 12.4 可观测与评测（LangSmith 类）— 不对客户，可对内

**未来目标**：托管多实例时，运营方统一看 trace。

**预留规则**：

- 所有检索与问答携带 `trace_id`（UUID，可选写入 log metadata）。  
- OpenTelemetry 导出点：`RetrievalOrchestrator.retrieve` 结束、`ConversationService` 生成结束。  
- Eval 结果格式稳定（`eval_runs.metrics_json`），便于未来同步到外部系统。  
- **不把 chunk 正文默认上报第三方**；集成需显式 env `OTEL_EXPORTER_*`。

### 12.5 完整 BI — 未做，须预留

**预留规则**：

- Analytics 接口返回结构化 JSON，不写死仅前端图表。  
- `retrieval_logs` / `eval_runs` 保留 `created_at` 索引，支持按日聚合。  
- 导出：Eval Run、Review 队列支持 CSV（M4+）。

### 12.6 检索优化高级能力 — 未做，须预留

| 能力 | 预留 |
|------|------|
| Rerank 模型 | Orchestrator 内 pluggable `Reranker` 接口 |
| LlamaIndex 适配 | `app/rag/adapters/` 目录约定 |
| A/B profile | `eval_runs.config_snapshot_json.profile_id` |
| Faithfulness LLM 评分 | `eval_runs.metrics_json.faithfulness_sample` 扩展键 |

### 12.7 SKU 与功能开关

| SKU | 说明 |
|-----|------|
| `standard` | KB + Lab + Eval（本期默认） |
| `full` | 含冻结 Canvas/策划等（遗留客户） |
| 未来 `enterprise` | SSO、部门 RBAC、Graph 模块开关 |

实现：`KB_SKU` env + `app_settings.feature_flags` JSON。

---

## 13. 里程碑排期建议

| 阶段 | 内容 | 目标 |
|------|------|------|
| Phase 1 | M1 + M2（M2-1～M2-5） | POC 可签、Eval 可演示 |
| Phase 2 | M2-6 + M3 + M5 | 第一个客户案例包 |
| Phase 3 | M4 | 第二客户可复制运营 |

---

## 14. 文档维护

| 变更类型 | 同步文档 |
|----------|----------|
| 新表/列 | DATABASE_SCHEMA.md + Alembic |
| 新 API | API_SPEC.md §Eval |
| UAT | DEMO.md、CUSTOMER_INSTALL.md |
| 检索行为 | RAG_SPEC.md |

---

## 15. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | 2026-08-07 | 初版：私有化交付 + Eval 闭环 + 后续预留 |
| 1.1 | 2026-08-07 | 用户流程、服务层、Eval 引擎、Pack 格式、M1 端点清单、实施任务分解 |

---

## 16. 角色与用户流程

### 16.1 角色

| 角色 | 典型人员 | 主界面 |
|------|----------|--------|
| 实施工程师 | 乙方交付 | Admin + deploy 文档 |
| 知识管理员 | 客户 IT/运营 | Admin Library / Lab / Eval |
| 业务用户 | 销售/策划 | Workspace 项目问答 |
| 审计员（可选） | 质量 | Admin 检索日志 + Eval 报告只读 |

### 16.2 实施工程师 — 新客户首日（SOP）

```text
1. 部署实例（deploy.sh + .env：LLM/Embedding/SECRET/INITIAL_ADMIN_*）
2. 登录 → 强制改密（若 M1-1 未自动强制，文档要求手工改）
3. Admin → 系统设置：确认模型、WEB_SEARCH_ENABLED=false（私有化默认）
4. 导入 Knowledge Pack（M3）或手工上传 3～5 份资料
5. 等待入库 indexed；失败项在资料页重试（M3）
6. Retrieval Lab：跑 Pack 内 3 条冒烟 query
7. Eval Center：导入 eval_set 模板 → Run → 截图报告
8. 创建项目 → Workspace 问答 2 轮 → 核对引用
9. 备份脚本试跑；交付签字表 + 版本 tag 记入台账
```

### 16.3 知识管理员 — 日常运营

```text
新资料上传 → 入库完成 → Lab 单条验证 →（可选）加入 eval_set
每周：Eval Run 回归；检索日志看零命中
收到 Review（M4）→ 补资料 / 同义词 → Replay Eval
```

### 16.4 业务用户

```text
项目列表 → 进入知识问答 → 阅读答案与引用 →（M4）反馈
```

---

## 17. 后端服务层设计

Router 薄层；业务逻辑入 Service（CLAUDE.md §13.3）。

| Service | 职责 | 里程碑 |
|---------|------|--------|
| `EvalService` | set/case CRUD；`run_set(set_id)` 调度；metrics 计算；写 eval_runs | M2 |
| `EvalScoringService` | Hit@k、DocHit@k、KeywordHit；单 case 判 pass | M2 |
| `RetrievalLabService` | 封装 Orchestrator + Context Pack 预览 DTO；写 log triggered_by=rag_hit_test | M2 |
| `KnowledgePackService` | 解析 Pack manifest；调 ImportService + DocumentService；可选导入 eval_set | M3 |
| `IngestionJobService` | 文档状态机；失败原因；retry_index(document_id) | M3 |
| `ReviewQueueService` | 规则入队；状态流转；转 eval_case | M4 |
| `SynonymService` | 加载 query_synonyms；expand_query（Orchestrator 前置） | M4 |
| `RetrievalProfileService` | 读 profile；合并 app_settings 默认 | M4 |

**Eval Run 执行逻辑（M2-3）**：

```text
POST /eval/runs
  → 创建 eval_runs(status=running)
  → 加载 eval_set + cases + 当前 config_snapshot（settings + profile + synonym_version）
  → FOR each case（顺序执行，避免 embedding 压垮；后续可 worker 化）:
        resolve project_id from set.project_id
        hits = RetrievalOrchestrator.search(..., triggered_by=eval_replay, eval_run_id=...)
        pass = EvalScoringService.score(case, hits)
        append per_case_results; 每条 case 可写 retrieval_log
  → 汇总 metrics_json
  → eval_runs.status=completed | failed
```

**失败处理**：单 case 异常不中断全 run；该 case `pass=false`，`error` 写入 per_case_results。

**预留**：异步 Celery/ARQ 跑 run（§12.4 trace_id 贯穿）。

---

## 18. 消息与追溯 metadata 规范（M1-7）

`messages.metadata_json`（assistant 消息）扩展：

```json
{
  "retrieval_log_ids": ["uuid"],
  "citations": [ { "index": 1, "chunk_id": "...", "title": "..." } ],
  "kb_meta": { "chunk_count": 3, "path": "kb", "web_used": false },
  "trace_id": "uuid"
}
```

`retrieval_logs.final_output_id`：存 `message.id`（字符串）。

**Citation 校验（L2，E2E）**：每个 citation 的 chunk_id/case_id 必须出现在对应 log 的 `retrieved_items_json` 内。

---

## 19. Knowledge Pack 格式（M3-1）

文件：`knowledge_pack.json` + `files/` 目录（ZIP 打包）。

```json
{
  "pack_version": "1.0",
  "name": "reference-b2b-demo",
  "description": "脱敏 B2B 演示包",
  "documents": [
    {
      "relative_path": "files/handbook.pdf",
      "title": "产品手册",
      "doc_category": "product",
      "project_id": null
    }
  ],
  "cases": [ { "title": "...", "tags": "...", "solution_summary": "..." } ],
  "talking_points": [ { "scene": "...", "content": "..." } ],
  "eval_set": {
    "name": "smoke-b2b",
    "cases": [
      {
        "query": "核心产品有哪些？",
        "expected_keywords": ["产品", "能力"],
        "notes": "导入后可在 Lab 绑定 chunk_id"
      }
    ]
  }
}
```

**导入顺序**：documents（上传+索引）→ cases → talking_points → eval_set。  
**幂等**：相同 `pack.name` + 内容 hash 可选跳过（M3 可选 `force=true`）。

**预留** §12.3：Pack 内 `ontology_seed` 字段（本期忽略）。

---

## 20. M1 Admin 鉴权端点清单（M1-2）

以下路由的 **写操作**（POST/PUT/PATCH/DELETE）须 `Depends(require_admin)`：

| Router | 路径模式 |
|--------|----------|
| settings | PUT /settings |
| documents | POST upload, DELETE, batch-delete, batch-index |
| cases, talking_points, industry_materials, pricing_experiences | 写 |
| templates, workflows, visual_styles, rules | 写 |
| eval（全部） | 全部 admin |
| users | POST（已有 register admin） |

**读操作**：M1 可保持 `get_current_user`；M4 可选收紧 cases 列表。

**前端**：`KB_SKU=standard` 时非 admin 访问 `/admin/settings` 重定向或 403 页。

---

## 21. 实施任务分解（研发 backlog）

> **v1.0 状态**：Phase 1（M1/M2）、Phase 2（M3/M5）已完成，见 §25。Phase 3（M4）为下一期。

任务 ID 与里程碑对应；PR 建议单任务或单模块。

### Phase 1 — M1 ✅

| Task | 内容 | 主要路径 |
|------|------|----------|
| T-M1-01 | config: INITIAL_ADMIN_*, SEED_DEMO_CONTENT | apps/api/app/core/config.py, init_db.py |
| T-M1-02 | require_admin 批量挂载 | apps/api/app/routers/*.py, main.py 可选分组 |
| T-M1-03 | KB_SKU 前端菜单 | admin-shell.tsx, middleware 或 layout |
| T-M1-04 | 向导文案/死代码清理 | projects/new/page.tsx |
| T-M1-05 | conversation metadata + log 扩展列 | conversation_service, alembic, retrieval model |
| T-M1-06 | retrieval-logs API/UI 关联 message | rag.py, retrieval-logs/page.tsx |
| T-M1-07 | test_knowledge_qa_flow | apps/api/app/tests/ |
| T-M1-08 | DEMO/CUSTOMER_INSTALL 更新 | docs/ |

### Phase 1 — M2 ✅

| Task | 内容 | 主要路径 |
|------|------|----------|
| T-M2-01 | Alembic eval_* + retrieval_logs 列 | alembic/, models/ |
| T-M2-02 | EvalService + Scoring | services/eval_*.py |
| T-M2-03 | routers/eval.py | routers/ |
| T-M2-04 | Lab scope + context preview API | rag.py or lab router |
| T-M2-05 | admin/eval 页面 | app/admin/eval/ |
| T-M2-06 | rag-test 增强 + 保存用例 | rag-test/page.tsx |
| T-M2-07 | test_eval_run_hit_at_k | tests/ |

### Phase 2 — M3/M5 ✅

| Task | 内容 |
|------|------|
| T-M3-01 | KnowledgePackService + POST /knowledge/packs/import |
| T-M3-02 | 资料页 chunk 列表 API + UI |
| T-M3-03 | onboarding wizard（Admin 首页） |
| T-M5-01 | reference pack 资源 + 案例稿 |

### Phase 3 — M4（下一期 ⬜）

| Task | 内容 |
|------|------|
| T-M4-01 | query_synonyms + SynonymService |
| T-M4-02 | retrieval_profiles |
| T-M4-03 | review_items + 规则入队 |
| T-M4-04 | analytics API + 页面 |
| T-M4-05 | chat 反馈 UI |

---

## 22. Eval 阈值与 app_settings

| key | 类型 | 默认 | 说明 |
|-----|------|------|------|
| `eval_default_top_k` | int | 8 | Run 与 Lab 默认 |
| `eval_pass_hit_rate_threshold` | float | 0.8 | 交付签字建议 |
| `eval_run_max_cases` | int | 200 | 防误操作 |
| `qa_retrieval_scope` | string | union | union / project_only |
| `review_auto_enqueue_zero_hits` | bool | true | M4 |

---

## 23. 与 RAG_SPEC 的衔接

本期在 [RAG_SPEC.md](./RAG_SPEC.md) 补充（实现时）：

- § 命中测试与 `/api/v1/rag/search` 参数：`scope`  
- § Eval replay 与 `triggered_by=eval_replay`  
- § Context Pack 预览字段定义  

不修改检索权重算法前，Eval 只验证**行为回归**，不验证**语义质量**。

---

## 24. 文档索引（本迭代）

| 文档 | 内容 |
|------|------|
| [KB_PRIVATE_DELIVERY_SPEC.md](./KB_PRIVATE_DELIVERY_SPEC.md) | 本文件：总纲 |
| [KB_CONSOLE_UI_SPEC.md](./KB_CONSOLE_UI_SPEC.md) | Admin/Workspace KB 标准版 UI |
| [API_SPEC.md](./API_SPEC.md) §23–25 | Eval / RAG 扩展 / Pack |
| [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) §6 | Eval 与 Review 表 |
| [TEST_PLAN.md](./TEST_PLAN.md) §KB-Case-Delivery | 测试用例清单 |

---

## 25. 版本发布与后续规划（kb-case-v1.0）

**Tag**：`kb-case-v1.0`（2026-08-11）  
**分支**：`hotfix-0625`（交付基线，合并前以 tag 为准）

### 25.1 本期已交付（v1.0）

| 里程碑 | 状态 | 验收要点 |
|--------|------|----------|
| M1 可安装可验收 | ✅ | Seed/鉴权/KB SKU/问答↔日志/E2E/DEMO |
| M2 可验证 | ✅ | Lab+Context Pack 预览/Eval 引擎/UI/Lab→用例/冒烟模板 |
| M3 快速介入 | ✅ | Pack 导入/chunk 预览/Admin 引导 |
| M5 案例包装 | ✅ | `delivery/reference-pack` + `reference-b2b-demo.zip` |
| M4 可运营 | ⬜ | 下一期 Phase 3 |

**自动化**：`test_kb_m1` / `test_knowledge_qa_flow` / `test_eval_run` / `test_knowledge_pack`（见 CUSTOMER_INSTALL §6）

### 25.2 下一期 backlog（Phase 3 — M4，第二客户前）

优先级建议：

| 序 | Task | 说明 | 依赖 |
|----|------|------|------|
| P0 | T-M4-03 Review 队列 | 零命中/低分/引用异常入队；Admin `/admin/review` | retrieval_logs |
| P0 | T-M4-02 失败→eval_case | Review 条目一键加入评测集 | Eval 已就绪 |
| P1 | T-M4-01 query_synonyms | 检索前 query 扩展 | Orchestrator 前置 hook |
| P1 | T-M4-04 Analytics 简版 | 7 日零命中 Top、eval 趋势、latency | retrieval_logs + eval_runs |
| P1 | T-M4-05 问答反馈 UI | chat 页问题类型 → Review | M4-03 |
| P2 | T-M4-04 retrieval_profiles | hybrid 权重/top_k 可配置 profile | app_settings |
| P2 | Lab scope 参数 | `scope=union/project_only` 与 API_SPEC 对齐 | rag.py |

### 25.3 长期预留（不在 v1.0）

- 多租户 SaaS、Skill 市场、GraphRAG、客户侧 LangSmith、完整 BI（见 §12）

### 25.4 升级与运维（M5-3 摘要）

1. 备份：`./scripts/backup.sh`（DB + storage）  
2. 升级：拉取 tag → `docker compose up -d --build` → Alembic head  
3. 升级后：导入或 Run 冒烟 eval_set，确认 `hit_at_k_rate` ≥ 阈值  
4. 回滚：恢复 DB 快照 + 前一 tag 镜像
