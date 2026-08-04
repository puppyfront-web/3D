# Canvas / Conversation Architecture Hardening Spec

## 背景

当前分支已经把产品主形态收敛为「项目 -> 单一 canvas 工作台」，但底层仍存在 3 类架构性风险：

1. `project conversation` 与 `node-scoped conversation` 只有展示层过滤，没有存储层和运行时隔离。
2. 数据库 schema authority 同时存在 Alembic 迁移、应用启动 `create_all()`、运行时 seed 三条路径。
3. 版本与来源追踪存在双写状态源和弱约束，影响导出、审计、节点级可信度。

这些问题会持续放大为：

- 节点对话串到全局对话
- 环境间 schema 漂移
- 当前版本指针不一致
- 节点内容来源无法精确追溯

## 目标

本次修复方案只解决架构边界，不扩产品范围。

### 目标 A：会话 scope 一等化

- 全局对话、节点对话在存储层可区分
- 历史读取、LLM 上下文构建、SSE 写入只针对当前 scope
- 不再依赖 `message.metadata.node_id` 作为主模型

### 目标 B：数据库 authority 单一化

- Alembic 成为唯一 schema authority
- 应用 runtime 不再执行 `create_all()`
- startup 只做幂等 seed，不做结构变更
- Docker 与本地开发路径一致

### 目标 C：版本状态单一真相源

- 当前版本只保留一个权威来源
- 版本切换、恢复、导出、画布读取都从同一锚点判断
- 数据库层提供最小必要约束，避免悬空或双 current

### 目标 D：来源追踪按消费节点落库

- 每个节点只挂自己消费的来源
- 外部来源、上传文档、AI 填充来源统一进入标准化 provenance 模型
- 导出和审核读取同一套来源关系

## 非目标

- 不重做产品交互
- 不引入消息队列或事件总线
- 不改现有三大板块的画布拓扑
- 不在本阶段引入多用户协同编辑

## 方案概览

## 一、Conversation Scope 模型重构

### 1.1 新增子线程/作用域实体

新增 `conversation_threads`（或 `conversation_scopes`）表：

- `id`
- `conversation_id`
- `scope_type`：`project` | `node`
- `scope_ref_id`：项目级为空，节点级为 `canvas_node.id`
- `status`
- `created_at`
- `updated_at`

约束：

- 每个 `conversation_id` 只能有一个 `project` scope
- 每个 `(conversation_id, scope_type, scope_ref_id)` 唯一

### 1.2 Message 改为归属 thread

`messages` 从：

- `conversation_id`

改为：

- `thread_id`
- 保留 `conversation_id` 仅作为兼容字段的过渡期冗余，最终删除或只读派生

### 1.3 运行时规则

- `GET /projects/{id}/conversation` 返回 project scope thread
- `GET /projects/{id}/conversation?node_id=...` 返回对应 node scope thread
- `POST /conversations/{thread_id}/chat/stream` 或等效 thread endpoint 只加载当前 thread 的历史
- `build_message_history()` 不再读整条 project conversation

### 1.4 兼容迁移

迁移分两步：

1. 建新表，迁旧消息到 project scope；已有 node 消息按 `metadata.node_id` 回填 node scope
2. 前后端切到 thread id 后，逐步下线旧的 metadata 过滤逻辑

## 二、Schema Authority 收口

### 2.1 唯一 authority

保留：

- Alembic migration

移除：

- runtime `Base.metadata.create_all()`

### 2.2 启动行为

容器入口：

- `alembic upgrade head`
- 启动 API

应用 lifespan：

- `seed_if_needed()`
- 技能注册

### 2.3 Seed 约束

seed 必须满足：

- 幂等
- 不隐式补列/补表
- 对失败给出明确错误，而不是静默修结构

### 2.4 本地开发路径

提供单独脚本：

- `scripts/dev_bootstrap.sh`

职责：

1. 检查数据库可用
2. 跑 `alembic upgrade head`
3. 跑 seed

## 三、版本模型收口

### 3.1 单一真相源

建议保留：

- `projects.current_version_id`

收敛策略：

- `project_versions.is_current` 改为派生值，或完全移除

原因：

- 项目级读取当前画布、导出、对话默认上下文都天然以 `project` 为根
- 单指针比多行标记更适合作为运行时锚点

### 3.2 一致性约束

- `projects.current_version_id` 增加 FK 到 `project_versions.id`
- 服务层保证 `current_version_id` 指向同项目版本
- 版本恢复和创建必须在单事务内切换锚点

### 3.3 读取规则

- 当前画布：只读 `projects.current_version_id`
- 历史画布：显式 `version_id`
- 前端 `isReadOnly` 由“请求 version 是否等于 current_version_id”推导

## 四、Provenance 模型收口

### 4.1 拆成记录层和关联层

新增：

- `source_records`
- `node_source_links`

`source_records` 保存标准化来源：

- `id`
- `source_type`
- `source_ref_id`
- `title`
- `url`
- `excerpt`
- `confidence`
- `metadata_json`

`node_source_links` 保存消费关系：

- `node_id`
- `source_record_id`
- `usage_type`：`input` | `supporting` | `generated_from`

### 4.2 生成链路要求

每次 group fill 后：

- AI 填充来源单独入一条 `source_record`
- 上传文档来源按命中的文档/片段入 `source_record`
- web_search 结果按命中的外部来源入 `source_record`
- 对实际消费的节点建立 `node_source_links`

### 4.3 降级策略

若当前 LLM 返回无法精确到 node 的 source mapping：

- 至少挂到该 group 的全部消费节点
- 禁止只挂到一个 anchor node

## 五、实施阶段

### Phase 1：运行边界收口

- 去掉 runtime `create_all()`
- 增加 seed-only startup
- 补全缺失迁移链

### Phase 2：conversation scope 重构

- 新增 thread 表
- API 改为按 thread 读写
- 前端持有 thread id

### Phase 3：版本状态收口

- 删/降级 `is_current`
- 统一 current version 读取锚点

### Phase 4：provenance 重构

- 新来源模型
- 画布 orchestrator 改为按节点挂来源

## 验收标准

1. 节点对话与全局对话在数据库层是不同 scope，不靠 metadata 推断
2. 启动 API 不会隐式建表，未迁移数据库直接 fail-fast
3. 当前版本只存在一个权威来源，读写一致
4. 任一节点都能查询到自身消费的来源，而不是借道 anchor node
5. Docker、本地开发、测试三条路径的 schema 行为一致
