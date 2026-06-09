# API_SPEC.md — 3D 展示幕墙 AI 专家系统 API 规格

> Last updated: 2026-06-09
> Base URL: `/api/v1`
> Authentication: JWT Bearer Token（MVP 阶段简化）
> Response Wrapper: `{ success: bool, data: T, message: string }`

---

## 1. 通用约定

### 1.1 统一响应格式

```json
// 成功
{ "success": true, "data": { ... }, "message": "OK" }

// 分页
{ "success": true, "data": { "items": [...], "total": 100, "page": 1, "page_size": 20 } }

// 错误
{ "success": false, "message": "错误描述" }
```

### 1.2 HTTP 状态码

| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 403 | 禁止（导出门控未通过、权限不足） |
| 404 | 资源不存在 |
| 409 | 冲突（如企业画像已存在） |
| 500 | 服务器错误 |

### 1.3 分页参数

所有列表接口支持：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| page | int | 1 | 页码 |
| page_size | int | 20 | 每页数量 |

---

## 2. 健康检查

### `GET /`

```json
{ "name": "3D Wall AI Platform", "version": "0.1.0", "status": "running" }
```

### `GET /health`

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "debug": true,
  "llm_provider": "mock",
  "embedding_provider": "mock",
  "image_provider": "mock"
}
```

---

## 3. Auth — `/api/v1/auth`

### POST /auth/login

登录认证（MVP 简化，邮箱即可）。

**Request:**
```json
{ "email": "admin@example.com" }
```

**Response:** `LoginResponse`
```json
{
  "token": "jwt-token-string",
  "user": { "id": "uuid", "email": "...", "name": "...", "role": { "id": "uuid", "name": "admin" } }
}
```

### POST /auth/logout

登出（JWT 无状态，客户端丢弃 token）。

---

## 4. Users — `/api/v1/users`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /users | 列表（page, page_size, search, role） |
| GET | /users/{id} | 详情 |
| POST | /users | 创建 |
| PUT | /users/{id} | 更新 |
| DELETE | /users/{id} | 删除 |

---

## 5. Projects — `/api/v1/projects`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /projects | 列表（status, company_id, priority） |
| GET | /projects/{id} | 详情 |
| POST | /projects | 创建 |
| PUT | /projects/{id} | 更新 |
| PATCH | /projects/{id}/status | 更新状态 |
| DELETE | /projects/{id} | 删除 |

**ProjectCreate:**
```json
{
  "name": "华为5G展厅项目",
  "description": "裸眼3D展示方案",
  "company_id": "uuid",
  "owner_id": "uuid",
  "priority": "high"
}
```

**项目状态流转：** `draft → in_progress → proposal_draft → review → completed → archived`

---

## 6. Companies — `/api/v1/companies`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /companies | 列表（search, industry） |
| GET | /companies/{id} | 详情 |
| POST | /companies | 创建 |
| PUT | /companies/{id} | 更新 |
| DELETE | /companies/{id} | 删除 |

---

## 7. Company Profiles — `/api/v1/company-profiles`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /company-profiles | 列表（company_id） |
| GET | /company-profiles/{id} | 详情 |
| GET | /company-profiles/by-company/{company_id} | 按企业查询 |
| POST | /company-profiles | 创建（每个企业限一条） |
| PUT | /company-profiles/{id} | 更新 |
| POST | /company-profiles/generate | AI 生成企业解析 |
| DELETE | /company-profiles/{id} | 删除 |

**POST /company-profiles/generate** 触发 AI 生成企业六看画像。请求：
```json
{
  "company_id": "uuid",
  "company_info": "华为，5G通信...",
  "requirement_text": "需要一个裸眼3D展示方案"
}
```

---

## 8. Documents — `/api/v1/documents`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /documents/upload | 上传文件（multipart, ?project_id=&auto_index=true） |
| GET | /documents | 列表（project_id, status） |
| GET | /documents/{id} | 详情 |
| POST | /documents/{id}/index | 手动触发索引 |
| POST | /documents/index-batch | 批量索引 |
| PUT | /documents/{id} | 更新元数据 |
| DELETE | /documents/{id} | 删除（级联删除 chunks） |

---

## 9. Cases — `/api/v1/cases`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /cases | 列表（project_id, industry, published_only, min_score） |
| GET | /cases/{id} | 详情 |
| POST | /cases | 创建 |
| PUT | /cases/{id} | 更新 |
| PATCH | /cases/{id}/quality-score | 更新质量评分 |
| POST | /cases/import | 导入（JSON/CSV 文件） |
| DELETE | /cases/{id} | 删除 |

---

## 10. Templates — `/api/v1/templates`

### Prompt Templates

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /templates/prompts | 列表（category） |
| GET | /templates/prompts/{id} | 详情 |
| POST | /templates/prompts | 创建 |
| PUT | /templates/prompts/{id} | 更新 |
| POST | /templates/prompts/import | 导入（JSON/TXT/MD） |
| DELETE | /templates/prompts/{id} | 删除 |

### Proposal Templates

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /templates/proposals | 列表（category） |
| GET | /templates/proposals/{id} | 详情 |
| POST | /templates/proposals | 创建 |
| PUT | /templates/proposals/{id} | 更新 |
| POST | /templates/proposals/import | 导入（JSON） |
| DELETE | /templates/proposals/{id} | 删除 |

---

## 11. Workflows — `/api/v1/workflows`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /workflows | 列表（is_active） |
| GET | /workflows/{id} | 详情 |
| POST | /workflows | 创建 |
| PUT | /workflows/{id} | 更新 |
| POST | /workflows/import | 导入（JSON） |
| DELETE | /workflows/{id} | 删除 |

---

## 12. Visual Styles — `/api/v1/visual-styles`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /visual-styles | 列表（layout） |
| GET | /visual-styles/{id} | 详情 |
| POST | /visual-styles | 创建 |
| PUT | /visual-styles/{id} | 更新 |
| POST | /visual-styles/import | 导入（JSON） |
| DELETE | /visual-styles/{id} | 删除 |

---

## 13. Rules — `/api/v1/rules`

### Technical Rules

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /rules/technical | 列表（category, severity） |
| GET | /rules/technical/{id} | 详情 |
| POST | /rules/technical | 创建 |
| PUT | /rules/technical/{id} | 更新 |
| POST | /rules/technical/import | 导入 |
| DELETE | /rules/technical/{id} | 删除 |

### Quality Rules

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /rules/quality | 列表（category） |
| GET | /rules/quality/{id} | 详情 |
| POST | /rules/quality | 创建 |
| PUT | /rules/quality/{id} | 更新 |
| POST | /rules/quality/import | 导入 |
| DELETE | /rules/quality/{id} | 删除 |

---

## 14. Generations — `/api/v1/generations`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /generations/tasks | 任务列表（project_id, task_type, status） |
| GET | /generations/tasks/{id} | 任务详情（含 outputs） |
| POST | /generations/tasks | 创建任务 |
| PATCH | /generations/tasks/{id} | 更新任务状态 |
| DELETE | /generations/tasks/{id} | 删除任务（级联 outputs） |
| GET | /generations/tasks/{id}/outputs | 任务输出列表 |
| GET | /generations/outputs/{id} | 输出详情 |
| **PUT** | **/generations/outputs/{id}** | **更新内容或 sections_meta（人工编辑）** |
| **PATCH** | **/generations/outputs/{id}/sections/{order}/status** | **更新章节审核状态（HITL）** |

### PUT /generations/outputs/{id} — 人工编辑

```json
// 更新内容
{ "content": "## 1. 需求理解\n（编辑后的内容）" }

// 更新 sections_meta
{ "sections_meta": [{ "id": "uuid", "title": "需求理解", "order": 1, "status": "draft" }] }
```

### PATCH /generations/outputs/{id}/sections/{order}/status — 章节审核

```json
{ "status": "approved", "reviewed_by": "admin" }
```

**status 取值：** `draft` / `review` / `approved`

审核通过时自动设置 `reviewed_by` 和 `reviewed_at`。

---

## 15. RAG — `/api/v1/rag`

### POST /rag/search — 混合检索

**Request:**
```json
{
  "query": "裸眼3D 商业综合体 案例",
  "top_k": 5,
  "project_id": "uuid",
  "retrieval_type": "hybrid"   // hybrid / keyword / vector
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "query": "...",
    "results": [
      { "chunk_id": "uuid", "document_id": "uuid", "content": "...", "score": 0.92 }
    ],
    "total": 3,
    "retrieval_type": "hybrid"
  }
}
```

检索结果自动写入 `retrieval_logs`。

---

## 16. Agents — `/api/v1/agents`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /agents/company-analysis/{company_id} | 运行企业解析 Skill |
| POST | /agents/proposal | 运行策划案生成 Skill |
| POST | /agents/visual-prompt | 运行视觉 Prompt 生成 Skill |
| POST | /agents/generate-image | 直接图片生成 |
| POST | /agents/pipeline/{project_id} | 运行完整 Pipeline |

### POST /agents/company-analysis/{company_id}

触发企业六看解析。参数：`force_regenerate`, `project_id`。

### POST /agents/proposal

```json
{ "project_id": "uuid" }
```

生成 10 章标准结构策划案，自动解析 `sections_meta`。

### POST /agents/visual-prompt

```json
{
  "project_id": "uuid",
  "style_preferences": "科技感、蓝色调",
  "width": 1920,
  "height": 1080
}
```

### POST /agents/generate-image

```json
{
  "prompt": "3D display wall in shopping mall, futuristic blue tones",
  "negative_prompt": "blurry, low quality",
  "width": 1920,
  "height": 1080
}
```

### POST /agents/pipeline/{project_id}

运行完整流程：企业解析 → 策划案 → 视觉方案。每步存储结果并更新项目状态。

---

## 17. Exports — `/api/v1/exports`

> **所有导出端点都执行 HITL 门控检查**。`sections_meta` 中所有章节状态必须为 `approved`，否则返回 403。

| 方法 | 路径 | 说明 | 返回 |
|------|------|------|------|
| POST | /exports/word/{task_id} | 导出 Word | FileResponse (.docx) |
| POST | /exports/pdf/{task_id} | 导出 PDF | FileResponse (.pdf) |
| POST | /exports/pptx/{task_id} | 导出 PPTX | FileResponse (.pptx) |

**403 门控拒绝响应：**
```json
{
  "detail": {
    "message": "导出前需完成审核",
    "blockers": ["章节「风险与待确认事项」未审核通过", "章节「项目目标」未审核通过"]
  }
}
```

---

## 18. Skills — `/api/v1/skills`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /skills | 列出所有已注册 Skill |
| GET | /skills/{skill_id} | 获取 Skill Manifest |
| POST | /skills/{skill_id}/execute | 执行 Skill |
| GET | /skills/executions | 执行历史（project_id, status） |
| GET | /skills/executions/{id} | 执行详情 |

### POST /skills/{skill_id}/execute

```json
{
  "input_data": { "project_id": "uuid" },
  "project_id": "uuid"
}
```

**内置 Skill 清单：**

| skill_id | 名称 | 分类 | 说明 |
|----------|------|------|------|
| company_analysis | 企业解析 | analysis | AI 生成企业六看画像 |
| proposal_generation | 策划案生成 | proposal | 10 章结构化策划案 |
| visual_prompt | 视觉 Prompt | visual | 生成视觉策略和 Prompt |
| image_generation | 图片生成 | visual | 文生图/图生图 |
| export | 方案导出 | export | Word/PDF/PPTX 导出 |

---

## 19. Conversations — `/api/v1/conversations`

### CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /conversations | 列表（status, limit） |
| POST | /conversations | 创建 |
| GET | /conversations/{id} | 详情（含消息） |
| PATCH | /conversations/{id} | 更新（重命名） |
| DELETE | /conversations/{id} | 归档 |

### Messages

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /conversations/{id}/messages | 消息历史（limit） |
| POST | /conversations/{id}/messages | 发送消息（非流式） |

### SSE Streaming

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /conversations/{id}/chat/stream | SSE 流式对话 |

**SSE 事件格式：**
```
data: {"type": "text_delta", "text": "正在分析"}
data: {"type": "content_block", "block": {"type": "skill_progress", "data": {...}}}
data: {"type": "done", "message_id": "uuid"}
```

### Actions & Upload

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /conversations/{id}/actions | 执行内联操作（skill 触发/表单提交/审核） |
| POST | /conversations/{id}/upload | 上传聊天附件（支持 PDF/图片/视频/文档） |

### Visual Concept — 版本树

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /conversations/{id}/version-tree | 获取视觉概念版本树 |
| GET | /conversations/{id}/artifacts/{node_id} | 获取版本节点产物 |
| GET | /conversations/{id}/artifacts/compare?node_a=&node_b= | 对比两个版本 |
| POST | /conversations/{id}/visual-concept-actions | 版本操作（rollback/branch/switch） |

---

## 20. Feedback — `/api/v1/feedback`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /feedback | 列表（project_id, user_id, min_rating, category） |
| GET | /feedback/{id} | 详情 |
| POST | /feedback | 创建 |
| PUT | /feedback/{id} | 更新 |
| DELETE | /feedback/{id} | 删除 |

---

## 21. Settings — `/api/v1/settings`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /settings | 获取设置（敏感值已脱敏） |
| PUT | /settings | 更新设置 |

---

## 22. API 端点统计

| 模块 | 端点数 |
|------|--------|
| Health | 2 |
| Auth | 2 |
| Users | 5 |
| Projects | 6 |
| Companies | 5 |
| Company Profiles | 7 |
| Documents | 7 |
| Cases | 7 |
| Templates | 12 |
| Workflows | 6 |
| Visual Styles | 6 |
| Rules | 12 |
| Generations | 9 |
| RAG | 1 |
| Agents | 5 |
| Feedback | 5 |
| Exports | 3 |
| Skills | 5 |
| Conversations | 14 |
| Settings | 2 |
| **合计** | **121** |
