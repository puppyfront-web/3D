# TEST_PLAN.md — 3D 展示幕墙 AI 专家系统测试计划

> Last updated: 2026-06-09
> 现有测试：6 个文件，89 个用例，全部通过
> 测试框架：pytest + httpx (async) | 前端：TypeScript 编译检查

---

## 1. 测试策略

### 1.1 测试分层

```
┌─────────────────────────────┐
│   E2E / 集成测试（手动）      │  ← 前端全流程走查
├─────────────────────────────┤
│   API 端点测试（httpx）       │  ← 重点补充
├─────────────────────────────┤
│   Service / Skill 单元测试   │  ← 重点补充
├─────────────────────────────┤
│   Model 单元测试             │  ← 已有基础覆盖
├─────────────────────────────┤
│   TypeScript 编译检查        │  ← CI 门控
└─────────────────────────────┘
```

### 1.2 原则

1. **Mock Provider 优先** — 测试使用 MockLLMService / MockEmbeddingService / MockImageService，不依赖外部 API
2. **SQLite 内存库** — 测试使用 aiosqlite 内存数据库，每次测试重建表结构
3. **不测 LLM 质量** — LLM 输出内容不可预测，只验证输出格式和引用记录
4. **前端以编译检查为主** — TypeScript 编译零错误是底线，交互逻辑依赖人工验证

---

## 2. 现有测试覆盖

| 测试文件 | 用例数 | 覆盖范围 |
|----------|--------|----------|
| conftest.py | — | 公共 fixtures（async db, client, mock services） |
| test_models.py | ~15 | 所有 Model 的 CRUD 创建和关联关系 |
| test_projects.py | ~15 | Project CRUD API + 分页 + 筛选 |
| test_cases.py | ~15 | Case CRUD + 质量评分 + 导入 |
| test_import_service.py | ~5 | CSV/JSON 导入解析 |
| test_rag.py | ~15 | 检索、切片、embedding、检索日志 |
| test_visual_concept.py | ~23 | VisualConcept Agent 全流程 |

**总计：89 个用例**

---

## 3. 缺口分析

### 3.1 后端缺口（优先级排序）

| 优先级 | 模块 | 缺失测试 | 说明 |
|--------|------|----------|------|
| P0 | generations router | HITL 端点 | PUT /outputs/{id}, PATCH /sections/{order}/status |
| P0 | exports router | 导出门控 | 未审核时返回 403，全部审核后正常导出 |
| P0 | proposal_generation | sections_meta 解析 | 验证 10 章 markdown 正确解析为 sections_meta |
| P1 | documents router | 上传 + 索引 | 文件上传、自动索引、手动索引、批量索引 |
| P1 | company_profiles router | 企业解析生成 | POST /generate 触发 AI 解析 |
| P1 | conversations router | SSE 流式对话 | 消息收发、意图路由、流式响应格式 |
| P1 | skills runner | Skill 执行引擎 | 注册、执行、日志记录 |
| P2 | templates router | Prompt/Proposal 模板 CRUD | 创建、更新、导入 |
| P2 | workflows router | SOP CRUD | 创建、更新、导入 |
| P2 | visual_styles router | 视觉风格 CRUD | |
| P2 | rules router | 技术/质量规则 CRUD | |
| P2 | feedback router | 反馈 CRUD | |
| P2 | export service | 文件生成 | Word/PDF/PPTX 生成内容验证 |
| P3 | auth router | 登录/登出 | MVP 简化认证 |
| P3 | settings router | 设置读写 | |

### 3.2 前端缺口

前端暂不写自动化测试。验证方式：

- **编译检查**：`npx tsc --noEmit` — 零错误是底线
- **人工验证**：按 UI_SPEC.md 中的页面清单逐页走查

---

## 4. 补充测试计划

### Phase 1：HITL 门控测试（P0）

> 这些是最近实现的 Human-in-the-Loop 功能，必须优先覆盖。

#### test_hitl.py — 章节审核 + 导出门控

```python
# test_sections_meta_parsing
- 10 章 markdown 正确解析为 10 条 sections_meta
- 缺少 ## 标题时不崩溃
- 特殊字符标题正常处理

# test_section_status_update
- PATCH /sections/{order}/status → draft → review → approved
- approved 时自动设置 reviewed_by / reviewed_at
- 非 approved 时清除 reviewed_by / reviewed_at
- 越界 order 返回 400

# test_output_content_update
- PUT /outputs/{id} 更新 content
- PUT /outputs/{id} 更新 sections_meta

# test_export_gate
- 未审核时 POST /exports/word/{task_id} 返回 403 + blockers
- 部分审核时 POST /exports/pdf/{task_id} 返回 403
- 全部审核后 POST /exports/pptx/{task_id} 返回 200 + 文件
- 无 sections_meta 的旧数据允许导出（兼容）
```

### Phase 2：核心 CRUD 测试（P1）

#### test_documents.py

```python
# test_upload_document
- 上传文件 → 201 + 返回 DocumentOut
- 上传时 auto_index=true → 自动触发索引
- project_id 关联正确

# test_index_document
- POST /documents/{id}/index → 切片 + embedding
- 二次索引 → 更新 chunks

# test_batch_index
- 按 project_id 批量索引
- 索引状态记录正确
```

#### test_company_profiles.py

```python
# test_generate_company_analysis
- POST /company-profiles/generate → 返回带 six_views 的 profile
- 重复生成（force_regenerate=true）覆盖旧数据
- 缺少企业信息时返回缺失提示
```

#### test_conversations.py

```python
# test_create_conversation
# test_send_message
# test_stream_chat — 验证 SSE 事件格式
# test_intent_routing — 企业解析/策划案/视觉生成意图识别
# test_upload_chat_file
```

#### test_skills_runner.py

```python
# test_list_skills — 返回 5 个内置 Skill
# test_execute_skill — 调用 proposal_generation
# test_skill_execution_log — 执行记录写入 skill_executions
```

### Phase 3：模板与配置测试（P2）

#### test_templates.py

```python
# test_prompt_template_crud
# test_proposal_template_crud
# test_import_prompt_templates
# test_import_proposal_templates
```

#### test_workflows.py

```python
# test_workflow_crud
# test_import_workflows
# test_sop_steps_structure
```

#### test_rules.py / test_visual_styles.py / test_feedback.py

标准 CRUD 测试，每个约 5-8 个用例。

### Phase 4：导出质量测试（P3）

#### test_exports_quality.py

```python
# test_word_export_content — 验证 docx 包含标题和段落
# test_pdf_export_content — 验证 pdf 可读
# test_pptx_export_content — 验证 pptx 包含正确数量的 slides
# test_export_with_empty_content — 返回错误
```

---

## 5. RAG 检索专项测试

现有 test_rag.py 已覆盖基础检索。需要补充的场景：

```python
# test_rag_case_retrieval
- 输入"商业综合体裸眼3D" → 命中相关案例
- 输入"汽车品牌发布" → 命中科技风案例
- 低质量案例（quality_score < 3）不优先

# test_rag_retrieval_logging
- 每次检索写入 retrieval_logs
- 记录 query, results_count, latency_ms

# test_rag_citation_tracking
- 生成结果记录 used_cases, used_documents, used_chunks
```

---

## 6. 测试命令

```bash
# 后端全部测试
cd apps/api && python -m pytest app/tests/ -v

# 单文件测试
python -m pytest app/tests/test_hitl.py -v

# 带覆盖率（需安装 pytest-cov）
python -m pytest app/tests/ --cov=app --cov-report=term-missing

# 前端类型检查
cd apps/web && npx tsc --noEmit

# 前端 lint
cd apps/web && npx next lint
```

---

## 7. CI 门控标准

| 检查项 | 标准 |
|--------|------|
| 后端测试 | 全部通过，0 失败 |
| TypeScript 编译 | 0 错误 |
| ESLint | 0 错误 |
| 数据库迁移 | `alembic upgrade head` 无报错 |

---

## 8. 手动验证清单

以下场景需要人工验证，不能自动化：

### 8.1 项目创建流程

- [ ] /workspace/projects — 项目列表渲染
- [ ] /workspace/projects/new — 创建向导 5 步表单
- [ ] /workspace/projects/{id}/overview — 项目概览

### 8.2 企业解析

- [ ] /workspace/projects/{id}/company-analysis — AI 生成 + 人工编辑
- [ ] 六看数据正确展示
- [ ] 重新生成覆盖旧数据

### 8.3 策划案编辑器

- [ ] /workspace/projects/{id}/proposal — 10 章结构渲染
- [ ] Section Badge 下拉菜单（通过/审核中/退回）
- [ ] 审核进度条更新
- [ ] 导出按钮门控（未审核时 disabled）
- [ ] Word/PDF/PPTX 导出文件可正常打开

### 8.4 视觉工作台

- [ ] /workspace/projects/{id}/visual — Prompt 生成
- [ ] 图片生成（Mock 模式）
- [ ] 视觉概念版本树

### 8.5 Chat 对话

- [ ] 意图识别路由到正确 Skill
- [ ] SSE 流式响应
- [ ] Action Buttons 可点击
- [ ] 视觉风格选择面板
- [ ] 文件上传

### 8.6 管理后台

- [ ] /admin/assets — 资料管理
- [ ] /admin/cases — 案例库
- [ ] /admin/sop-workflows — SOP 配置
- [ ] /admin/proposal-templates — 策划案模板
- [ ] /admin/prompt-templates — Prompt 模板
- [ ] /admin/visual-styles — 视觉风格
- [ ] /admin/technical-rules — 技术规则
- [ ] /admin/quality-rules — 质量规则

---

## 9. 目标覆盖率

| 阶段 | 新增用例 | 总用例 | 覆盖重点 |
|------|----------|--------|----------|
| 现状 | — | 89 | Model + Project + Case + RAG + VisualConcept |
| Phase 1 完成后 | +20 | ~109 | HITL 门控 + sections_meta + 导出 |
| Phase 2 完成后 | +30 | ~139 | Document + CompanyProfile + Conversation + Skills |
| Phase 3 完成后 | +25 | ~164 | Templates + Workflows + Rules + VisualStyles |
| Phase 4 完成后 | +8 | ~172 | 导出质量 |
