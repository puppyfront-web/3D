# 项目需求规格 (PROJECT_SPEC)

> 本文档是 CLAUDE.md 的详细补充，涵盖项目目标、产品形态、核心原则、MVP 范围和数据模型的完整定义。

---

## 1. 行业背景

3D 展示幕墙、裸眼 3D、LED 媒体立面、数字视觉展示是一个高度定制化的行业。每个项目涉及：

- 客户企业品牌理解
- 场地条件分析
- 屏幕硬件参数
- 视觉创意策划
- 内容制作和投放
- 施工和验收

企业多年积累的 PPT、策划案、项目案例、图片素材、SOP、Prompt 和生图方法，目前散落在各个文件夹和个人电脑中，无法系统化复用和优化。

---

## 2. 核心用户角色

| 角色 | 主要场景 | 使用频率 |
|------|----------|----------|
| 销售 | 创建项目、录入客户信息、查看解析报告、导出方案给客户 | 高 |
| 策划 | 生成策划案、编辑策划案、查阅案例库、维护模板 | 高 |
| 设计 | 生成视觉方案、调 Prompt、生图、视觉风格管理 | 高 |
| 项目经理 | 审核方案、跟踪项目进度、协调反馈 | 中 |
| 审核人员 | 质量审核、评估效果、反馈闭环 | 中 |
| 管理员 | 管理后台配置、SOP 维护、用户权限 | 低 |

---

## 3. 产品形态详述

### 3.1 内部 AI 工作台

面向所有内部用户的主入口。以项目为核心组织所有工作。

核心能力：

1. **项目创建向导** — 结构化表单引导录入客户企业信息、项目需求、场地屏幕信息和视觉偏好
2. **企业解析报告** — 基于录入信息和上传资料，AI 生成企业画像和项目方向分析
3. **策划案工作台** — 文档编辑器形态，AI 生成 + 人工编辑，右侧 Agent 助手辅助
4. **视觉创意工作台** — Prompt 编辑 + 图片生成 + 多版本管理
5. **审核与导出** — 人工审核检查项 + 导出 Word/PDF

### 3.2 专家能力管理后台

面向管理员和资深策划/设计人员。管理所有可配置的专家能力。

核心能力：

1. **资料管理** — 上传、分类、标签管理
2. **案例库管理** — 结构化案例录入、质量评分、复用权重
3. **SOP 流程配置** — 工作流步骤定义、检查项配置、版本管理
4. **策划案模板** — 模板编辑、变量定义、场景适配
5. **Prompt 模板** — 正向/负向模板、变量、风格标签
6. **视觉风格库** — 风格定义、示例图片、参数配置
7. **技术规则库** — 行业技术规范、参数校验规则
8. **质量评估标准** — 评分维度、权重配置、标准描述

### 3.3 外部客户门户（预留）

MVP 不实现，但必须预留数据模型和接口设计。

未来功能：

1. **需求提交页** — 客户自主填写项目需求
2. **已审核方案查看** — 只能查看经内部审核通过的方案
3. **反馈提交** — 客户修改意见和确认

访问控制规则：

- 外部客户只能访问通过 `external_token` 关联且 `approved_for_external=true` 的内容
- 不能看到内部 Prompt、SOP、案例权重、评估记录
- 不能看到未审核的 AI 原始输出

---

## 4. MVP 功能清单

### 4.1 必须实现

#### P0 — 核心流程

- [ ] 创建项目（向导式表单）
- [ ] 录入企业信息
- [ ] 录入项目需求
- [ ] 录入场地与屏幕信息
- [ ] 上传资料
- [ ] 生成企业解析报告
- [ ] 生成策划案
- [ ] 生成视觉 Prompt
- [ ] 文生图 / 图生图接口预留
- [ ] 人工审核
- [ ] 导出 Word / PDF

#### P1 — 管理后台

- [ ] 资料管理 CRUD
- [ ] 案例库管理 CRUD
- [ ] SOP 流程配置
- [ ] 策划案模板管理
- [ ] Prompt 模板管理
- [ ] 视觉风格库管理
- [ ] 技术规则库
- [ ] 质量评估标准

#### P2 — RAG 基础

- [ ] 文档上传和解析
- [ ] chunk 切分
- [ ] embedding 入库
- [ ] 混合检索
- [ ] 检索日志
- [ ] 引用追溯

#### P3 — 反馈与评估

- [ ] 人工反馈保存
- [ ] 效果评估页
- [ ] 基础评估数据

### 4.2 明确不做

- 复杂多租户系统
- 拖拽式工作流编排
- 完整知识图谱
- 自动报价系统
- 最终施工图生成
- 最终投屏视频制作
- 复杂 BI 看板
- 外部客户自助完整生成
- 模型微调训练
- 复杂 A/B 测试系统

---

## 5. 数据模型完整定义

### 5.1 users

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| email | String(255) | 邮箱，唯一 |
| name | String(100) | 姓名 |
| role_id | FK → roles | 角色 |
| avatar_url | String(500) | 头像 |
| is_active | Boolean | 是否启用 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 5.2 roles

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| name | String(50) | 角色名称 |
| permissions_json | JSON | 权限配置 |

### 5.3 projects

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| name | String(200) | 项目名称 |
| description | Text | 项目描述 |
| status | Enum | 项目状态 |
| company_id | FK → companies | 关联企业 |
| owner_id | FK → users | 负责人 |
| screen_info_json | JSON | 屏幕信息 |
| site_info_json | JSON | 场地信息 |
| visual_preferences_json | JSON | 视觉偏好 |
| external_token | String(100) | 外部访问令牌 |
| external_status | Enum | 外部状态 |
| shared_at | DateTime | 共享时间 |
| approved_for_external | Boolean | 是否允许外部访问 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 5.4 companies

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| name | String(200) | 企业名称 |
| industry | String(100) | 行业 |
| contact_person | String(100) | 联系人 |
| contact_phone | String(50) | 联系电话 |
| contact_email | String(255) | 联系邮箱 |
| website | String(500) | 企业网站 |
| address | String(500) | 企业地址 |
| notes | Text | 备注 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 5.5 company_profiles

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| company_id | FK → companies | 关联企业 |
| industry | String(100) | 行业 |
| business_type | String(100) | 业务类型 |
| core_products | JSON | 核心产品/服务 |
| brand_keywords | JSON | 品牌关键词 |
| target_audience | Text | 目标客户 |
| communication_goal | Text | 传播目标 |
| visual_preferences | JSON | 视觉偏好 |
| forbidden_expressions | JSON | 禁忌表达 |
| missing_info | JSON | 待补充信息 |
| analysis_json | JSON | 完整分析结果 |
| status | Enum | 状态（草稿/已确认） |
| version | Integer | 版本号 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 5.6 cases

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| title | String(200) | 案例标题 |
| client_industry | String(100) | 客户行业 |
| project_type | String(100) | 项目类型 |
| scene | String(100) | 场景 |
| business_goal | String(200) | 商业目标 |
| screen_type | String(100) | 屏幕类型 |
| visual_style | String(100) | 视觉风格 |
| creative_theme | String(200) | 创意主题 |
| solution_summary | Text | 方案概述 |
| success_points | JSON | 亮点 |
| risks | JSON | 风险 |
| quality_score | Float | 质量评分 0-100 |
| reuse_weight | Float | 复用权重 0-1 |
| status | Enum | 状态 |
| tags | JSON | 标签 |
| cover_image_url | String(500) | 封面图 |
| attachments_json | JSON | 附件 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 5.7 documents

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| project_id | FK → projects | 关联项目（可选） |
| case_id | FK → cases | 关联案例（可选） |
| title | String(200) | 文档标题 |
| file_path | String(500) | 文件路径 |
| file_type | String(50) | 文件类型 |
| file_size | BigInteger | 文件大小 |
| parse_status | Enum | 解析状态 |
| parsed_text | Text | 解析后文本 |
| metadata_json | JSON | 元数据 |
| created_at | DateTime | 创建时间 |

### 5.8 document_chunks

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| document_id | FK → documents | 关联文档 |
| case_id | FK → cases | 关联案例（可选） |
| chunk_text | Text | chunk 文本 |
| section_title | String(200) | 章节标题 |
| page_number | Integer | 页码 |
| chunk_type | String(50) | chunk 类型 |
| metadata_json | JSON | 元数据 |
| embedding | Vector(1536) | 向量嵌入 |
| created_at | DateTime | 创建时间 |

### 5.9 prompt_templates

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| name | String(200) | 模板名称 |
| task_type | String(100) | 任务类型 |
| scene | String(100) | 场景 |
| visual_style | String(100) | 视觉风格 |
| positive_template | Text | 正向模板 |
| negative_template | Text | 负向模板 |
| variables_json | JSON | 变量定义 |
| quality_score | Float | 质量评分 |
| status | Enum | 状态 |
| usage_count | Integer | 使用次数 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 5.10 sop_workflows

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| name | String(200) | 流程名称 |
| workflow_type | String(100) | 流程类型 |
| version | String(50) | 版本号 |
| steps_json | JSON | 步骤定义 |
| checklist_json | JSON | 检查项 |
| status | Enum | 状态 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 5.11 generation_outputs

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| project_id | FK → projects | 关联项目 |
| output_type | Enum | 输出类型（企业解析/策划案/视觉/Prompt） |
| content_json | JSON | 输出内容 |
| used_cases | JSON | 引用案例 ID 列表 |
| used_documents | JSON | 引用文档 ID 列表 |
| used_chunks | JSON | 引用 chunk ID 列表 |
| used_sop_version | String(50) | 使用的 SOP 版本 |
| used_prompt_templates | JSON | 使用的 Prompt 模板 ID 列表 |
| status | Enum | 状态（生成中/已完成/已编辑/已审核） |
| version | Integer | 版本号 |
| created_by | FK → users | 创建人 |
| reviewed_by | FK → users | 审核人 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 5.12 retrieval_logs

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_query | Text | 用户查询 |
| structured_query_json | JSON | 结构化查询 |
| retrieved_items_json | JSON | 检索结果 |
| selected_context_json | JSON | 最终选用的上下文 |
| final_output_id | FK → generation_outputs | 关联的生成输出 |
| retrieval_method | String(50) | 检索方法 |
| latency_ms | Integer | 耗时 |
| created_at | DateTime | 创建时间 |

### 5.13 feedback

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| output_id | FK → generation_outputs | 关联输出 |
| user_id | FK → users | 反馈用户 |
| rating | Integer | 评分 1-5 |
| comment | Text | 评论 |
| feedback_type | Enum | 反馈类型（整体/章节/图片） |
| section_key | String(100) | 章节标识 |
| created_at | DateTime | 创建时间 |

### 5.14 其他模型

- `proposal_templates` — 策划案模板
- `visual_styles` — 视觉风格库
- `technical_rules` — 技术规则
- `quality_rules` — 质量标准
- `generation_tasks` — 生成任务队列
- `images` — 图片资源

---

## 6. 开发阶段计划

### Phase 1：工程与 UI 骨架（1-2 周）

- 创建 monorepo 结构
- 前端 Next.js 项目初始化
- 后端 FastAPI 项目初始化
- 数据库连接和基础模型
- 基础布局（侧边栏 + 内容区）
- workspace 路由和 admin 路由
- Mock 数据填充页面骨架

### Phase 2：后台配置能力（1-2 周）

- 资料管理 CRUD API + 页面
- 案例库管理 CRUD API + 页面
- SOP 配置
- 策划案模板管理
- Prompt 模板管理
- 视觉风格库管理
- 技术规则库

### Phase 3：RAG 基础能力（1-2 周）

- 文档上传 API
- 文档解析（PDF/PPT/Word）
- chunk 切分策略
- embedding 生成和入库
- 混合检索接口（关键词 + 向量）
- Context Pack 组装
- 检索日志

### Phase 4：Agent 工作流（1-2 周）

- 企业解析 Agent
- 策划案生成 Agent
- 视觉 Prompt 生成 Agent
- 图片生成 Provider 抽象
- 生成结果保存和引用追溯

### Phase 5：审核与反馈（1 周）

- 人工编辑界面
- 质量检查自动提示
- 反馈评分保存
- Word / PDF 导出
- 效果评估页

---

## 7. 外部客户门户预留设计

### 7.1 数据模型预留

- `projects.external_token` — 用于外部访问的唯一令牌
- `projects.approved_for_external` — 是否允许外部访问
- `projects.shared_at` — 共享时间
- `projects.external_status` — 外部状态

### 7.2 访问控制规则

```text
外部用户可以：
  - 通过 token 访问已审核方案
  - 提交反馈和修改意见
  - 查看方案的基本信息

外部用户不能：
  - 看到未经审核的内容
  - 看到内部 Prompt / SOP / 案例权重
  - 看到其他客户的项目
  - 直接修改方案内容
```

### 7.3 路由预留

```text
/portal/request          — 客户需求提交
/portal/project/[token]  — 客户查看方案（需 token）
```

---

## 8. 验收标准

MVP 验收时，系统至少应该做到：

1. ✅ 内部用户可以创建项目
2. ✅ 可以填写企业信息和项目需求
3. ✅ 可以生成并编辑企业解析报告
4. ✅ 可以维护资料、案例、SOP、Prompt 和模板
5. ✅ 可以基于企业画像和 RAG 生成策划案
6. ✅ 策划案能显示引用案例和待确认项
7. ✅ 可以生成视觉策略和 Prompt
8. ✅ 可以接入或模拟文生图 / 图生图
9. ✅ 可以保存生成结果和人工反馈
10. ✅ 可以导出方案文档
11. ✅ 后台可以查看基础评估数据
12. ✅ 系统结构为后续外部客户门户预留扩展空间
