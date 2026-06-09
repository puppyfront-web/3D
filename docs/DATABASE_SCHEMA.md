# DATABASE_SCHEMA.md — 3D 展示幕墙 AI 专家系统数据库设计

> Last updated: 2026-06-09
> Migration version: 010_fix_prompt_templates.py（10 个迁移）
> ORM: SQLAlchemy 2.0 + async | Database: PostgreSQL + pgvector

---

## 1. ER 关系总览

```
roles ──1:N──> users
                    │
companies ──1:1──> company_profiles
companies ──1:N──> projects <── users (owner)
                         │
                         ├──1:N──> documents ──1:N──> document_chunks
                         ├──1:N──> cases
                         ├──1:N──> generation_tasks ──1:N──> generation_outputs (self-ref: parent_output_id)
                         ├──1:N──> feedback
                         ├──1:N──> conversations ──1:N──> messages
                         └──1:N──> skill_executions <── skills

standalone tables: technical_rules, quality_rules, prompt_templates,
                   proposal_templates, visual_styles, sop_workflows,
                   retrieval_logs, app_settings
```

---

## 2. 表结构详情

### 2.1 users / roles — 用户与角色

#### roles

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| name | String(100) | UNIQUE, NOT NULL | 角色名 |
| description | Text | | 角色描述 |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

#### users

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| email | String(255) | UNIQUE, INDEX, NOT NULL | 登录邮箱 |
| name | String(255) | NOT NULL | 用户名 |
| avatar_url | String(500) | | 头像 |
| role_id | UUID | FK → roles.id, NOT NULL | 角色 |
| is_active | Boolean | NOT NULL, default true | 是否启用 |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

---

### 2.2 companies / company_profiles — 企业与画像

#### companies

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| name | String(255) | INDEX, NOT NULL | 企业名称 |
| industry | String(100) | | 行业 |
| website | String(500) | | 官网 |
| description | Text | | 企业简介 |
| logo_url | String(500) | | Logo |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

#### company_profiles

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| company_id | UUID | FK → companies.id, UNIQUE, INDEX | 一对一 |
| strengths | Text | | 优势 |
| weaknesses | Text | | 劣势 |
| market_position | Text | | 市场定位 |
| key_products | Text | | 核心产品 |
| competitors | Text | | 竞争对手 |
| recent_news | Text | | 近期动态 |
| culture | Text | | 企业文化 |
| financials | Text | | 财务概况 |
| raw_analysis | Text | | AI 原始分析文本 |
| six_views | JSON | | 企业六看结构化分析（向后看/向前看/向左看/向右看/向上看/向下看） |
| technology_arch | JSON | | 技术一张图（分层架构） |
| project_background | JSON | | 项目背景（宏观→中观→微观） |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

**six_views JSON 结构：**
```json
{
  "backward_history": { "founding": "...", "origin": "...", "core_philosophy": "..." },
  "forward_planning": { "strategy": "...", "product_roadmap": "...", "market_expansion": "..." },
  "left_competitors": { "benchmark_companies": "...", "differentiation": "..." },
  "right_industry": { "trends": "...", "market_landscape": "..." },
  "upward_policy": { "national_policy": "...", "local_policy": "..." },
  "downward_niche": { "core_advantage": "...", "irreplaceability": "..." }
}
```

---

### 2.3 projects — 项目

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| name | String(255) | NOT NULL | 项目名 |
| description | Text | | 项目需求描述 |
| company_id | UUID | FK → companies.id, INDEX, NOT NULL | 所属企业 |
| owner_id | UUID | FK → users.id, INDEX, NOT NULL | 负责人 |
| status | String(50) | NOT NULL, default "draft" | draft / in_progress / proposal_draft / review / completed / archived |
| priority | String(50) | | 优先级 |
| external_token | String(255) | UNIQUE | 外部客户访问令牌 |
| external_status | String(50) | | 外部可见状态 |
| shared_at | DateTime(tz) | | 共享时间 |
| approved_for_external | Boolean | NOT NULL, default false | 是否允许外部查看 |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

**项目状态流转：**
```
draft → in_progress → proposal_draft → review → completed → archived
```

---

### 2.4 documents / document_chunks — 文档与向量

#### documents

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| project_id | UUID | FK → projects.id, INDEX | 所属项目（可为空=公共资料） |
| filename | String(500) | NOT NULL | 存储文件名 |
| original_filename | String(500) | NOT NULL | 原始文件名 |
| content_type | String(100) | NOT NULL | MIME 类型 |
| file_size | Integer | NOT NULL | 字节数 |
| file_path | String(1000) | NOT NULL | 磁盘路径 |
| title | String(500) | | 文档标题 |
| status | String(50) | NOT NULL, default "pending" | pending / indexed / failed |
| chunk_count | Integer | NOT NULL, default 0 | 切片数 |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

#### document_chunks

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| document_id | UUID | FK → documents.id, INDEX, NOT NULL | 所属文档 |
| content | Text | NOT NULL | 切片文本 |
| chunk_index | Integer | NOT NULL | 切片序号 |
| page_number | Integer | | 页码 |
| token_count | Integer | NOT NULL, default 0 | Token 数 |
| metadata_json | Text | | 元数据 JSON |
| embedding | Vector(1536) / Text | | pgvector 向量（降级为 Text） |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

**级联：** 删除 document → 级联删除所有 chunks

---

### 2.5 cases — 案例库

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| project_id | UUID | FK → projects.id, INDEX, NOT NULL | 关联项目 |
| title | String(500) | NOT NULL | 案例标题 |
| client_name | String(255) | NOT NULL | 客户名 |
| industry | String(100) | | 行业 |
| challenge | Text | | 客户挑战 |
| solution | Text | | 解决方案 |
| results | Text | | 成果 |
| technologies | Text | | 使用技术 |
| duration | String(100) | | 项目周期 |
| team_size | Integer | | 团队规模 |
| budget_range | String(100) | | 预算范围 |
| quality_score | Float | | 质量评分 |
| is_published | Boolean | NOT NULL, default false | 是否发布 |
| tags | Text | | 标签 |
| reference_images | JSON | | 参考图片列表 |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

---

### 2.6 generation_tasks / generation_outputs — 生成任务与产物

#### generation_tasks

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| project_id | UUID | FK → projects.id, INDEX, NOT NULL | 所属项目 |
| type | String(100) | NOT NULL | proposal / visual / review / evaluation |
| status | String(50) | NOT NULL, default "pending" | pending / running / completed / failed |
| prompt_used | Text | | 使用的 prompt（截断前 500 字） |
| model_used | String(100) | | 使用的模型 |
| error_message | Text | | 错误信息 |
| started_at | DateTime(tz) | | 开始时间 |
| completed_at | DateTime(tz) | | 完成时间 |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

#### generation_outputs

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| task_id | UUID | FK → generation_tasks.id, INDEX, NOT NULL | 所属任务 |
| content_type | String(100) | NOT NULL, default "text/plain" | text/plain, text/markdown, image/png |
| content | Text | NOT NULL | 生成内容（markdown / 图片 URL） |
| used_cases | JSON | default [] | 引用的案例 ID 列表 |
| used_documents | JSON | default [] | 引用的文档 ID 列表 |
| used_chunks | JSON | default [] | 引用的 chunk ID 列表 |
| used_sop_version | String(50) | | 使用的 SOP 版本 |
| sections_meta | JSON | default [] | 章节审核元数据（见下方结构） |
| version | Integer | NOT NULL, default 1 | 版本号 |
| parent_output_id | UUID | FK → generation_outputs.id | 上一版本（版本历史） |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

**sections_meta JSON 结构（Human-in-the-Loop）：**
```json
[
  {
    "id": "uuid",
    "title": "需求理解",
    "order": 1,
    "status": "draft",        // draft / review / approved
    "reviewed_by": null,       // 审核人
    "reviewed_at": null        // 审核时间 ISO8601
  }
]
```

**级联：** 删除 task → 级联删除所有 outputs

---

### 2.7 feedback — 反馈

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| project_id | UUID | FK → projects.id, INDEX, NOT NULL | 所属项目 |
| user_id | UUID | FK → users.id, INDEX, NOT NULL | 反馈人 |
| generation_task_id | UUID | FK → generation_tasks.id | 关联生成任务 |
| rating | Integer | NOT NULL | 评分 1-5 |
| comment | Text | | 评论 |
| category | String(100) | | 反馈类别 |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

---

### 2.8 skills / skill_executions — 技能与执行日志

#### skills

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| skill_id | String(100) | UNIQUE, INDEX, NOT NULL | 技能唯一标识 |
| name | String(255) | NOT NULL | 技能名称 |
| description | Text | | 描述 |
| category | String(100) | NOT NULL | 分类 |
| manifest_json | JSON | | Skill Manifest |
| input_schema_json | JSON | | 输入 Schema |
| output_schema_json | JSON | | 输出 Schema |
| required_services_json | JSON | | 依赖服务 |
| permissions_json | JSON | | 权限 |
| visibility | String(50) | NOT NULL, default "internal" | internal / public |
| version | String(50) | NOT NULL, default "1.0.0" | 版本 |
| status | String(50) | NOT NULL, default "active" | active / disabled / deprecated |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

#### skill_executions

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| skill_id | UUID | FK → skills.id, INDEX, NOT NULL | 执行的技能 |
| project_id | UUID | FK → projects.id, INDEX | 关联项目 |
| user_id | UUID | FK → users.id, INDEX | 执行人 |
| input_json | JSON | | 输入参数 |
| output_json | JSON | | 输出结果 |
| status | String(50) | NOT NULL, default "running" | running / completed / failed |
| error_message | Text | | 错误信息 |
| duration_ms | Integer | | 执行时长 |
| used_cases | JSON | | 引用案例 |
| used_documents | JSON | | 引用文档 |
| used_chunks | JSON | | 引用 chunk |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| completed_at | DateTime(tz) | | 完成时间 |

**级联：** 删除 skill → 级联删除所有 executions

---

### 2.9 conversations / messages — 对话与消息

#### conversations

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| project_id | UUID | FK → projects.id, INDEX, ondelete SET NULL | 关联项目 |
| title | String(500) | NOT NULL, default "新对话" | 对话标题 |
| status | String(50) | INDEX, NOT NULL, default "active" | active / archived |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

#### messages

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| conversation_id | UUID | FK → conversations.id, INDEX, ondelete CASCADE, NOT NULL | 所属对话 |
| role | String(20) | NOT NULL | user / assistant / system |
| content | Text | NOT NULL, default "" | 消息文本 |
| content_type | String(50) | NOT NULL, default "text" | text / rich |
| rich_content | JSON | | 结构化内容块（ContentBlock 数组） |
| skill_execution_id | UUID | FK → skill_executions.id, ondelete SET NULL | 关联技能执行 |
| metadata_json | JSON | | 元数据 |
| created_at | DateTime(tz) | NOT NULL, default now() | |

**级联：** 删除 conversation → 级联删除所有 messages

---

### 2.10 配置表（standalone）

#### sop_workflows

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| name | String(255) | NOT NULL | SOP 名称 |
| description | Text | | 描述 |
| version | String(50) | NOT NULL, default "1.0" | 版本 |
| steps | JSON | default [] | 步骤定义（含 order/name/agent/inputs/outputs/rules） |
| pipeline_stages | JSON | | Pipeline 阶段定义 |
| is_active | Boolean | NOT NULL, default true | 是否启用 |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

#### prompt_templates

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| name | String(255) | NOT NULL | 模板名 |
| description | Text | | 描述 |
| category | String(100) | NOT NULL | 分类（generation / visual / analysis） |
| template_text | Text | NOT NULL | 模板内容 |
| variables | JSON | default [] | 变量列表 |
| is_default | Boolean | NOT NULL, default false | 是否默认 |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

#### proposal_templates

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| name | String(255) | NOT NULL | 模板名 |
| description | Text | | 描述 |
| category | String(100) | NOT NULL | 分类 |
| sections | JSON | default {} | 章节结构 |
| is_default | Boolean | NOT NULL, default false | 是否默认 |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

#### visual_styles

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| name | String(255) | NOT NULL | 风格名 |
| description | Text | | 描述 |
| primary_color | String(20) | NOT NULL, default "#1a73e8" | 主色 |
| secondary_color | String(20) | | 辅色 |
| accent_color | String(20) | | 强调色 |
| background_color | String(20) | | 背景色 |
| font_primary | String(100) | | 主字体 |
| font_secondary | String(100) | | 辅字体 |
| layout | String(50) | | 布局风格 |
| brand_guidelines | Text | | 品牌规范 |
| material_spec | JSON | | 材质规范参数 |
| lighting_spec | JSON | | 灯光规范参数 |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

#### technical_rules / quality_rules

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| name | String(255) | NOT NULL | 规则名 |
| category | String(100) | NOT NULL | 分类 |
| description | Text | | 描述 |
| rule_text | Text | NOT NULL | 规则内容 |
| severity (tech) | String(50) | NOT NULL, default "warning" | info / warning / error |
| weight (quality) | Float | NOT NULL, default 1.0 | 权重 |
| is_active | Boolean | NOT NULL, default true | 是否启用 |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

---

### 2.11 retrieval_logs — 检索日志

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| query | Text | NOT NULL | 检索查询 |
| retrieval_type | String(50) | NOT NULL | hybrid / keyword / vector |
| results_count | Integer | NOT NULL, default 0 | 返回数量 |
| top_scores | JSON | default [] | Top 得分 |
| document_ids | JSON | default [] | 命中文档 |
| latency_ms | Integer | | 耗时 ms |
| created_at | DateTime(tz) | NOT NULL, default now() | |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

### 2.12 app_settings — 应用设置

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| key | String(100) | PK | 设置键 |
| value | Text | NOT NULL, default "" | 设置值 |
| updated_at | DateTime(tz) | NOT NULL, onupdate now() | |

> 唯一使用非 UUID 主键的表。

---

## 3. 级联关系汇总

| 父表 | 子表 | 行为 |
|------|------|------|
| documents | document_chunks | cascade all, delete-orphan |
| generation_tasks | generation_outputs | cascade all, delete-orphan |
| skills | skill_executions | cascade all, delete-orphan |
| conversations | messages | cascade all, delete-orphan |
| projects → conversations | project_id | ondelete SET NULL |
| conversations → messages | conversation_id | ondelete CASCADE |
| messages → skill_executions | skill_execution_id | ondelete SET NULL |

---

## 4. 外键关系图

```
roles.id                ← users.role_id
companies.id            ← projects.company_id
companies.id            ← company_profiles.company_id (UNIQUE)
users.id                ← projects.owner_id
projects.id             ← documents.project_id
projects.id             ← cases.project_id
projects.id             ← feedback.project_id
projects.id             ← generation_tasks.project_id
projects.id             ← conversations.project_id
projects.id             ← skill_executions.project_id
users.id                ← feedback.user_id
users.id                ← skill_executions.user_id
documents.id            ← document_chunks.document_id
generation_tasks.id     ← generation_outputs.task_id
generation_tasks.id     ← feedback.generation_task_id
generation_outputs.id   ← generation_outputs.parent_output_id (self-ref)
skills.id               ← skill_executions.skill_id
conversations.id        ← messages.conversation_id
skill_executions.id     ← messages.skill_execution_id
```

---

## 5. 预留字段说明

以下字段为外部客户门户预留（MVP 不实现完整功能，但数据模型已就绪）：

- `projects.external_token` — 外部访问令牌
- `projects.external_status` — 外部可见状态
- `projects.shared_at` — 共享时间
- `projects.approved_for_external` — 是否允许外部查看

外部客户未来只能访问已审核内容，不能看到 AI 原始输出、内部 Prompt、案例权重等。
