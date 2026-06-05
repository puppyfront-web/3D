# 3D 展示幕墙 AI 专家系统开发规则与需求说明

## 1. 项目目标

本项目是一个面向 3D 展示幕墙、裸眼 3D、LED 媒体立面、数字视觉展示行业的 AI Native 专家系统。

系统 MVP 阶段主要面向企业内部用户，包括销售、策划、设计、项目经理和审核人员。后续版本会扩展为对外客户使用的需求提交门户和客户协同确认系统。

本项目不是一个通用 AI 聊天机器人，也不是一个简单的"上传文档 + 问答"工具。

核心目标是建设：

```text
内部 AI 方案工作台
+ 专家能力管理后台
+ RAG 知识库
+ SOP 工作流
+ 策划案专家 Agent
+ 视觉创意专家 Agent
+ 人工审核与反馈闭环
```

系统需要帮助企业将多年沉淀的 PPT、策划案、项目案例、图片素材、SOP、Prompt、生图方法和技术规则，转化为可配置、可检索、可复用、可持续优化的行业专家能力。

详细需求规格见 [docs/PROJECT_SPEC.md](docs/PROJECT_SPEC.md)。

---

## 2. 产品形态

系统采用一个统一平台，两类入口。

```text
3D 展示幕墙 AI 专家系统
├─ 内部 AI 工作台
└─ 专家能力管理后台
```

后续预留：

```text
外部客户门户
├─ 客户需求提交
├─ 已审核方案查看
└─ 修改意见反馈
```

MVP 阶段只做内部用户体验版，不直接开放给终端客户使用。

---

## 3. 核心原则

开发时必须遵守以下原则。

### 3.1 不做通用聊天机器人

主交互不是 ChatGPT 式单一对话框。

正确交互形态是：

```text
项目工作台
+ 结构化表单
+ 企业解析报告
+ 策划案文档编辑器
+ 视觉生成工作台
+ 右侧 Agent 助手
```

对话框只能作为辅助面板，用于追问、解释、局部修改和优化建议，不能作为系统唯一主界面。

### 3.2 专家能力必须可配置

以下内容不得硬编码在代码里：

```text
SOP 流程
Prompt 模板
策划案模板
案例权重
视觉风格
技术规则
质量评估标准
企业画像字段
```

这些内容必须通过管理后台维护。

### 3.3 RAG 必须可追溯

所有用于生成的资料都必须能追溯来源。

策划案生成时，需要记录：

```text
引用了哪些案例
引用了哪些文档
引用了哪些 chunk
使用了哪个 SOP 版本
使用了哪个模板
使用了哪个 Prompt 模板
```

禁止生成无法追溯的虚构案例。

### 3.4 AI 输出必须可审核

AI 生成内容不能直接作为最终交付结果。

所有 AI 生成内容都必须支持：

```text
人工编辑
人工审核
版本保存
反馈评分
导出前检查
```

尤其是涉及以下内容时必须提示人工确认：

```text
报价
工期
屏幕参数
施工条件
最终投屏效果
技术可行性
客户承诺
```

### 3.5 缺失信息必须提示

如果用户没有提供关键资料，不允许模型编造。

必须标记：

```text
需要进一步确认
```

例如：

```text
屏幕尺寸需要进一步确认
主观看点需要进一步确认
预算范围需要进一步确认
交付周期需要进一步确认
```

---

## 4. MVP 范围

### 4.1 MVP 必须实现

MVP 阶段需要实现以下能力。

#### 内部 AI 工作台

```text
项目列表
创建项目向导
企业信息录入
项目需求录入
场地与屏幕信息录入
视觉偏好选择
资料上传
企业解析报告生成
策划案生成与编辑
视觉 Prompt 生成
文生图 / 图生图接口预留或接入
审核与导出
人工反馈
```

#### 专家管理后台

```text
资料管理
案例库管理
SOP 流程配置
策划案模板管理
Prompt 模板管理
视觉风格库管理
技术规则库
质量评估标准
效果评估
```

#### RAG 知识库

```text
文档上传
文档解析
chunk 切分
embedding 入库
案例结构化
图片标签管理
Prompt 模板检索
混合检索
检索日志
引用追溯
```

### 4.2 MVP 暂不实现

以下功能不要在 MVP 第一版实现，除非明确要求：

```text
复杂多租户系统
拖拽式工作流编排
完整知识图谱
自动报价系统
最终施工图生成
最终投屏视频制作
复杂 BI 看板
外部客户自助完整生成
模型微调训练
复杂 A/B 测试系统
```

---

## 5. 推荐技术栈

### 5.1 前端

```text
Next.js App Router
TypeScript
TailwindCSS
shadcn/ui 风格组件
React Hook Form
Zod
```

### 5.2 后端

```text
FastAPI
SQLAlchemy
Alembic
Pydantic
PostgreSQL
pgvector
```

### 5.3 AI 能力

```text
OpenAI-compatible LLM Provider
OpenAI-compatible Embedding Provider
Image Generation Provider 抽象接口
Mock Provider 用于本地开发
```

### 5.4 存储

MVP 第一版：

```text
本地 storage 目录
PostgreSQL
pgvector
```

后续可替换为：

```text
阿里云 OSS
S3
MinIO
Qdrant
Milvus
```

---

## 6. 推荐项目目录结构

```text
3d-wall-ai-agent/
├─ apps/
│  ├─ web/
│  │  ├─ app/
│  │  │  ├─ workspace/
│  │  │  │  ├─ projects/
│  │  │  │  ├─ projects/new/
│  │  │  │  └─ projects/[id]/
│  │  │  │     ├─ overview/
│  │  │  │     ├─ company-analysis/
│  │  │  │     ├─ proposal/
│  │  │  │     ├─ visual/
│  │  │  │     ├─ review/
│  │  │  │     └─ exports/
│  │  │  │
│  │  │  ├─ admin/
│  │  │  │  ├─ assets/
│  │  │  │  ├─ cases/
│  │  │  │  ├─ sop-workflows/
│  │  │  │  ├─ proposal-templates/
│  │  │  │  ├─ prompt-templates/
│  │  │  │  ├─ visual-styles/
│  │  │  │  ├─ technical-rules/
│  │  │  │  ├─ quality-rules/
│  │  │  │  └─ evaluations/
│  │  │  │
│  │  │  └─ portal/
│  │  │     ├─ request/
│  │  │     └─ project/[token]/
│  │  │
│  │  ├─ components/
│  │  │  ├─ layout/
│  │  │  ├─ workspace/
│  │  │  ├─ admin/
│  │  │  ├─ proposal/
│  │  │  ├─ visual/
│  │  │  └─ agent/
│  │  │
│  │  ├─ lib/
│  │  └─ types/
│  │
│  └─ api/
│     ├─ app/
│     │  ├─ main.py
│     │  ├─ core/
│     │  ├─ db/
│     │  ├─ models/
│     │  ├─ schemas/
│     │  ├─ routers/
│     │  ├─ services/
│     │  ├─ rag/
│     │  ├─ agents/
│     │  ├─ workflows/
│     │  ├─ parsers/
│     │  ├─ exporters/
│     │  └─ tests/
│     └─ pyproject.toml
│
├─ docs/
│  ├─ PROJECT_SPEC.md
│  ├─ UI_SPEC.md
│  ├─ RAG_SPEC.md
│  ├─ AGENT_SPEC.md
│  ├─ DATABASE_SCHEMA.md
│  ├─ API_SPEC.md
│  └─ TEST_PLAN.md
│
├─ docker-compose.yml
├─ .env.example
├─ CLAUDE.md
└─ README.md
```

---

## 7. 前端 UI 要求

详细 UI 规格见 [docs/UI_SPEC.md](docs/UI_SPEC.md)。

### 7.1 总体交互原则

前端主界面必须是项目流程驱动，而不是单纯聊天。

标准流程：

```text
创建项目
↓
填写企业信息
↓
填写项目需求
↓
上传资料
↓
生成企业解析
↓
生成策划案
↓
生成视觉方案
↓
审核与导出
↓
反馈沉淀
```

### 7.2 内部 AI 工作台页面

#### 项目列表页

路径：`/workspace/projects`

功能：

```text
查看项目列表
按状态筛选
搜索客户企业
创建新项目
进入项目详情
```

项目状态：

```text
待补充资料
企业解析中
企业解析已完成
策划案已生成
视觉方案已生成
待审核
已导出
已归档
```

#### 创建项目向导

路径：`/workspace/projects/new`

分步骤表单：

```text
Step 1：客户企业信息
Step 2：项目需求
Step 3：场地与屏幕信息
Step 4：视觉偏好
Step 5：上传资料
```

必须避免只让用户输入一句话。

#### 企业解析页

路径：`/workspace/projects/[id]/company-analysis`

必须展示：

```text
企业基础信息
行业与场景分析
品牌定位
产品 / 服务特点
目标客户
项目目标
推荐视觉方向
待补充信息
```

必须支持：

```text
AI 生成
人工编辑
重新生成
确认企业画像
```

#### 策划案生成页

路径：`/workspace/projects/[id]/proposal`

页面形态：文档编辑器 + 右侧 Agent 助手

策划案结构建议：

```text
需求理解
企业解析摘要
项目背景
项目目标
创意主题
方案亮点
视觉方向
参考案例
实施建议
风险与待确认事项
```

必须支持：

```text
生成完整策划案
重新生成单个章节
人工编辑
查看引用来源
保存版本
导出 Word / PDF
```

#### 视觉创意页

路径：`/workspace/projects/[id]/visual`

页面形态：视觉配置区 + Prompt 编辑区 + 图片结果区

必须支持：

```text
选择视觉风格
选择 Prompt 模板
上传参考图
上传场地图
生成视觉策略
生成正向 Prompt
生成负向 Prompt
调用生图接口
展示多版本图片
人工反馈
保存可用版本
```

#### 审核与导出页

路径：`/workspace/projects/[id]/review`

导出前必须显示检查项：

```text
企业解析是否确认
是否引用真实案例
是否存在缺失参数
是否包含未经确认的报价
是否包含未经确认的工期
视觉结果是否人工确认
```

### 7.3 管理后台页面

后台路径统一放在 `/admin`

必须实现：

```text
/admin/assets
/admin/cases
/admin/sop-workflows
/admin/proposal-templates
/admin/prompt-templates
/admin/visual-styles
/admin/technical-rules
/admin/quality-rules
/admin/evaluations
```

---

## 8. 数据模型要求

详细数据库设计见 [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md)。

MVP 至少包含以下模型。

```text
users
roles
projects
companies
company_profiles
documents
document_chunks
cases
images
prompt_templates
sop_workflows
proposal_templates
visual_styles
technical_rules
quality_rules
generation_tasks
generation_outputs
retrieval_logs
feedback
```

### 8.1 projects

必须预留未来外部客户门户字段：

```text
external_token
external_status
shared_at
approved_for_external
```

外部客户不能访问未审核内容。

### 8.2 company_profiles

企业画像字段：

```text
company_id
industry
business_type
core_products
brand_keywords
target_audience
communication_goal
visual_preferences
forbidden_expressions
missing_info
analysis_json
```

### 8.3 cases

案例库字段：

```text
title
client_industry
project_type
scene
business_goal
screen_type
visual_style
creative_theme
solution_summary
success_points
risks
quality_score
reuse_weight
status
```

案例必须支持质量评分和复用权重。

### 8.4 document_chunks

字段：

```text
document_id
case_id
chunk_text
section_title
page_number
chunk_type
metadata_json
embedding
```

### 8.5 prompt_templates

字段：

```text
name
task_type
scene
visual_style
positive_template
negative_template
variables_json
quality_score
status
```

### 8.6 sop_workflows

字段：

```text
name
workflow_type
version
steps_json
checklist_json
status
```

### 8.7 generation_outputs

必须记录：

```text
project_id
output_type
content_json
used_cases
used_documents
used_chunks
used_sop_version
used_prompt_templates
status
```

---

## 9. RAG 设计规则

详细 RAG 规格见 [docs/RAG_SPEC.md](docs/RAG_SPEC.md)。

### 9.1 不要做一个大杂烩知识库

知识资产必须分层：

```text
文档知识库
结构化案例库
图片案例库
Prompt 模板库
SOP 工作流库
技术规则库
质量标准库
企业画像库
```

### 9.2 检索流程

必须按以下链路实现：

```text
用户需求
↓
任务识别
↓
需求结构化
↓
检索意图改写
↓
元数据过滤
↓
关键词检索
↓
向量检索
↓
简单 rerank
↓
Context Pack 组装
↓
Agent 生成
```

### 9.3 Context Pack

不要把检索结果原样塞给模型。

必须组装结构化上下文：

```text
企业画像
项目需求
匹配案例
引用文档
相关 chunk
Prompt 模板
技术规则
SOP 检查项
待确认信息
```

### 9.4 检索日志

每次检索必须写入 `retrieval_logs`，记录：

```text
user_query
structured_query_json
retrieved_items_json
selected_context_json
final_output_id
```

---

## 10. Agent 工作流要求

详细 Agent 规格见 [docs/AGENT_SPEC.md](docs/AGENT_SPEC.md)。

### 10.1 企业解析模块

企业解析是策划案和视觉生成的前置步骤。

输入：

```text
企业信息
项目需求
客户资料
上传文档
用户补充说明
```

输出：

```text
企业基础画像
行业场景分析
品牌定位
产品服务特点
目标客户
项目目标
推荐视觉方向
待补充信息
```

结果必须保存为 `company_profiles`。

### 10.2 策划案专家 Agent

执行流程：

```text
读取项目需求
↓
读取企业画像
↓
读取 SOP
↓
RAG 检索案例和文档
↓
检索技术规则
↓
生成策划案大纲
↓
生成完整策划案
↓
执行质量检查
↓
保存输出
```

输出必须包含：

```text
需求理解
企业解析摘要
项目目标
创意主题
方案亮点
视觉方向
参考案例
实施建议
风险与待确认事项
```

禁止：

```text
编造案例
编造报价
编造屏幕参数
编造工期
承诺最终投屏效果
```

### 10.3 视觉创意专家 Agent

执行流程：

```text
读取项目需求
↓
读取企业画像
↓
读取视觉风格库
↓
检索相似视觉案例
↓
选择 Prompt 模板
↓
生成视觉策略
↓
生成正向 Prompt
↓
生成负向 Prompt
↓
调用图片生成接口
↓
保存图片和 Prompt
↓
记录人工反馈
```

输出必须包含：

```text
视觉策略
正向 Prompt
负向 Prompt
构图建议
参考案例
注意事项
生成图片
```

---

## 11. API 模块要求

详细 API 规格见 [docs/API_SPEC.md](docs/API_SPEC.md)。

后端 API 按模块拆分：

```text
auth
users
projects
companies
company_profiles
assets
documents
cases
prompt_templates
sop_workflows
proposal_templates
visual_styles
technical_rules
quality_rules
rag
agents
generation_outputs
feedback
exports
evaluations
```

API 逻辑必须放在 service 层，不要把业务逻辑堆在 router 里。

---

## 12. 代码质量规则

### 12.1 通用规则

```text
不要写死业务配置
不要写死模型 Provider
不要写死 Prompt
不要写死 SOP
不要写死文件路径
不要把 AI 调用散落在业务代码中
```

必须使用 service 抽象：

```text
LLMService
EmbeddingService
ImageGenerationService
RetrievalService
DocumentParserService
ExportService
```

### 12.2 前端规则

```text
页面只负责展示和交互
业务请求放到 lib/api
复杂表单使用独立组件
状态标签统一组件化
Agent 助手组件复用
不要在页面里写大量 mock 逻辑
```

### 12.3 后端规则

```text
Router 只处理请求响应
Service 处理业务逻辑
Model 只定义数据结构
Schema 负责输入输出校验
RAG 逻辑放到 rag 模块
Agent 逻辑放到 agents 或 workflows 模块
```

---

## 13. Claude Code 工作规则

### 13.1 写代码前必须先计划

每次任务开始时，必须先输出：

```text
理解的需求
涉及的文件
数据库变更
API 变更
前端页面变更
测试计划
潜在风险
```

在用户确认前，不要直接大规模写代码。

### 13.2 一次只做一个任务包

不要一次性实现整个系统。

推荐任务顺序：

```text
Task 0：工程骨架
Task 1：数据库模型
Task 2：基础布局和路由
Task 3：资料管理
Task 4：案例库管理
Task 5：模板和配置后台
Task 6：文档解析
Task 7：RAG 检索
Task 8：企业解析
Task 9：策划案 Agent
Task 10：视觉创意 Agent
Task 11：导出和反馈
Task 12：效果评估
```

### 13.3 每次修改后必须自检

每次完成任务后必须执行：

```text
类型检查
lint
单元测试
必要的 API 测试
前端页面基础检查
```

并输出：

```text
修改了哪些文件
实现了什么功能
如何测试
测试结果
还缺什么
```

---

## 14. 测试要求

### 14.1 后端测试

必须覆盖：

```text
数据库模型创建
CRUD API
文件上传
文档解析
RAG 检索
企业画像生成
策划案生成
Prompt 生成
反馈保存
导出功能
```

### 14.2 RAG 测试

必须构造测试数据，验证：

```text
输入商业综合体裸眼 3D 需求，能命中相关案例
输入汽车品牌发布需求，能命中汽车或科技风案例
低质量案例默认不优先进入结果
检索结果能够写入 retrieval_logs
生成结果能够记录引用来源
```

### 14.3 前端测试重点

必须人工检查：

```text
项目创建流程是否顺畅
企业解析页面是否可编辑
策划案页面是否像文档编辑器
视觉生成页面是否像图片工作台
后台配置是否清晰
Agent 助手是否只是辅助，而不是主界面
```

---

## 15. UI 风格要求

整体风格：

```text
专业
科技感
企业级
干净
重内容编辑
重项目流程
```

建议：

```text
主色：深蓝 / 石墨黑
强调色：电光蓝 / 青色
背景：浅灰白
卡片：白底、轻阴影、圆角
按钮：主次分明
```

不要做成娱乐化、生图社区风格。

---

## 16. 外部客户门户预留规则

MVP 不实现完整外部客户系统，但必须预留设计。

外部客户未来只能访问：

```text
需求提交页
已审核方案查看页
反馈提交页
```

外部客户不能看到：

```text
未经审核的 AI 原始输出
内部 Prompt
内部 SOP
案例权重
内部评估记录
未公开案例资料
```

项目表必须预留：

```text
external_token
approved_for_external
shared_at
external_status
```

---

## 17. 禁止事项

开发中禁止出现以下情况：

```text
把系统做成纯聊天页面
把 SOP 写死在 Prompt 中
把 Prompt 模板写死在代码中
把案例权重写死在代码中
AI 输出不保存引用来源
AI 生成内容不能编辑
没有人工审核直接导出
没有资料缺失提示
没有反馈闭环
对外客户直接看到原始生成结果
```

---

## 18. 第一阶段开发任务

### Phase 1：工程与 UI 骨架

```text
创建 monorepo
创建前后端项目
创建数据库连接
创建基础布局
创建 workspace 路由
创建 admin 路由
使用 mock 数据完成页面骨架
```

### Phase 2：后台配置能力

```text
资料管理
案例库管理
SOP 配置
策划案模板
Prompt 模板
视觉风格库
技术规则库
```

### Phase 3：RAG 基础能力

```text
文档上传
文档解析
chunk 切分
embedding 入库
检索接口
Context Pack
检索日志
```

### Phase 4：Agent 工作流

```text
企业解析
策划案生成
视觉 Prompt 生成
图片生成 Provider 抽象
生成结果保存
```

### Phase 5：审核与反馈

```text
人工编辑
质量检查
反馈评分
Word / PDF 导出
效果评估页
```

---

## 19. 给 Claude Code 的第一条启动 Prompt

执行项目时，先使用以下 Prompt：

```text
请阅读 CLAUDE.md，并严格按照其中的项目目标、产品形态、代码规则和任务拆分执行。

当前任务不是直接写完整系统，而是先完成项目规划和工程骨架。

请先不要写代码，先输出：
1. 你对项目的理解
2. 推荐目录结构
3. 前端页面清单
4. 后端模块清单
5. 数据库模型清单
6. 第一阶段开发计划
7. 测试计划
8. 你认为需要确认的问题

注意：
- 本项目不是 ChatGPT 式聊天应用。
- MVP 面向内部用户。
- 主交互是项目工作台，不是单一对话框。
- 后台需要支持客户调整 SOP、Prompt、模板、案例权重、视觉风格和质量标准。
- RAG 检索必须可追溯。
- AI 输出必须可编辑、可审核、可反馈。
```

---

## 20. 最终验收标准

MVP 验收时，系统至少应该做到：

```text
1. 内部用户可以创建项目
2. 可以填写企业信息和项目需求
3. 可以生成并编辑企业解析报告
4. 可以维护资料、案例、SOP、Prompt 和模板
5. 可以基于企业画像和 RAG 生成策划案
6. 策划案能显示引用案例和待确认项
7. 可以生成视觉策略和 Prompt
8. 可以接入或模拟文生图 / 图生图
9. 可以保存生成结果和人工反馈
10. 可以导出方案文档
11. 后台可以查看基础评估数据
12. 系统结构为后续外部客户门户预留扩展空间
```

---

这份 `CLAUDE.md` 的核心作用是约束 Claude Code：**不要把项目做成普通 AI 聊天应用，而是按"内部 AI 工作台 + 专家管理后台 + 可运营专家能力"的方向生成代码。**
