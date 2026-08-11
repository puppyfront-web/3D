# KB 标准版控制台 UI 规格 (KB_CONSOLE_UI_SPEC)

> **版本**: 1.0  
> **更新**: 2026-08-07  
> **上位**: [KB_PRIVATE_DELIVERY_SPEC.md](./KB_PRIVATE_DELIVERY_SPEC.md)  
> **视觉基线**: [UI_SPEC.md](./UI_SPEC.md)（颜色、字体、组件仍用 shadcn 体系）

---

## 1. 适用范围

- `KB_SKU=standard`（默认）下的 Admin 与 Workspace 主路径。  
- `KB_SKU=full` 时恢复现有完整 Admin 侧栏（Canvas 相关入口仍可不展示，由 `CANVAS_ENABLED` 控制）。

---

## 2. 设计原则（KB 标准版）

1. **运营优先**：Admin 首屏指向「资料 → 测检索 → 跑评测」。  
2. **可追溯可见**：问答引用、检索日志、Eval 失败项均可点击到 chunk/文档。  
3. **不 ChatGPT 化主 Admin**：Lab/Eval 是表单+结果列表，不是自由聊天。  
4. **Workspace 以项目问答为主界面**（`/workspace/chat/{id}`）。

---

## 3. Admin 侧栏（standard SKU）

分组展示（可折叠）：

```text
概览                    /admin

知识库
  资料管理              /admin/assets
  案例库                /admin/cases
  话术库                /admin/talking-points

检索与质量
  检索实验室            /admin/rag-test      （Lab，M2 增强）
  评测中心              /admin/eval          （M2 新增）
  检索日志              /admin/retrieval-logs

系统
  系统设置              /admin/settings      （仅 admin 角色可见入口）

--- 以下 standard 默认隐藏 ---
  行业资料、SOP、方案模板、Prompt、视觉、技术/质量规则、报价经验、评估记录(legacy)
```

**legacy `评估记录`（/admin/evaluations）**：与 Eval Center 并存时，standard 隐藏；full SKU 可保留。M4 评估语义统一进 Review/Eval。

**实现**：`admin-shell.tsx` 读取 `NEXT_PUBLIC_KB_SKU` 或构建时 env 过滤 `ADMIN_LINKS`。

---

## 4. 页面规格

### 4.1 概览 `/admin`

| 区块 | 内容 |
|------|------|
| 状态卡片 | 资料总数 / indexed / failed；最近 24h 检索次数；最近 eval_run 通过率 |
| 快捷操作 | 上传资料、打开 Lab、运行默认 eval_set |
| 首次引导（M3） | 未完成 onboarding 时显示 4 步 wizard banner |

### 4.2 检索实验室 `/admin/rag-test`

**布局**：

```text
┌─ 查询区 ─────────────────────────────────────┐
│ query [____]  project [可选▼]  scope [union▼]   │
│ top_k [8]     [检索]                            │
├─ 结果 hits ────────────────────────────────────┤
│  #1 score  title  source  [查看 chunk]          │
├─ Context Pack 预览（M2，可折叠）─────────────────┤
│  模拟进 LLM 的文本块（与 QA 一致）               │
├─ 操作 ─────────────────────────────────────────│
│  [保存为评测用例] → 选择 eval_set               │
└────────────────────────────────────────────────┘
```

**空状态**：提示先上传资料并完成 indexed。

**错误**：Embedding/Provider 未配置时，链到系统设置。

### 4.3 评测中心 `/admin/eval`

**Tab：评测集 | 运行记录**

**评测集列表**：

- 列：名称、用例数、绑定 project、最近 run 通过率、操作（编辑/Run/导入模板）  
- 新建集：name、description、optional project_id  

**用例编辑（抽屉或子页）**：

| 字段 | 必填 | 说明 |
|------|------|------|
| query | 是 | |
| expected_chunk_ids | 否 | UUID 列表，Lab 可回填 |
| expected_document_ids | 否 | |
| expected_keywords | 否 | |
| notes | 否 | |

**Run 详情页** `/admin/eval/runs/[id]`：

- metrics 卡片：hit_at_k_rate、empty_rate、latency p50/p95  
- 失败用例表：query、原因（miss_hit / keyword / empty）、top_k 摘要  
- 操作：导出 JSON；**与上一 run 对比**（M2 可选，Phase 2）  

### 4.4 检索日志 `/admin/retrieval-logs`

增强（M1/M2）：

- 筛选：`triggered_by`、`conversation_id`、`message_id`、`eval_run_id`  
- 行展开：`retrieved_items_json` 摘要  
- 链接：`message_id` → Workspace 对话深链（若可行）或 modal 展示原问答  

### 4.5 资料管理 `/admin/assets`

M3 增强：

- 列：状态 pending/indexed/failed、chunk_count、失败原因 tooltip  
- 行操作：重试索引、**查看 chunks**（抽屉列表）  
- 批量：上传、批量索引（admin）

### 4.6 系统设置 `/admin/settings`

- 非 admin 用户不显示侧栏入口；直链访问显示无权限页。  
- 分组：LLM、Embedding、检索后端（FastGPT）、联网搜索、Eval 默认阈值（M2）。

---

## 5. Workspace

### 5.1 项目列表 `/workspace/projects`

- 卡片 CTA：**进入知识问答**（非 Canvas）。  
- 创建项目：轻量向导（M1-4）。

### 5.2 知识问答 `/workspace/chat/[projectId]`

| 元素 | 说明 |
|------|------|
| Header | 项目名 + 返回列表 |
| 消息列表 | assistant 展示引用卡片 [1][2] |
| 引用区 | 标题、snippet、来源类型 |
| 输入框 | 多轮 |
| 反馈（M4） | 「有问题」→ 类型：未命中/引错/过时/其他 |

**metadata 只读展示（可选 debug 模式）**：admin 可看 retrieval_log_id。

---

## 6. 响应式与无障碍

- Admin 表格小屏横向滚动；Lab/Eval 查询区垂直堆叠。  
- 引用链接具备 `aria-label`（来源标题）。

---

## 7. 后续 UI 预留（本期不实现）

| 模块 | 路径预留 | 规格位置 |
|------|----------|----------|
| Review 队列 | `/admin/review` | KB_PRIVATE_DELIVERY M4 |
| Analytics | `/admin/analytics` | §12.5 |
| Optimize 同义词 | `/admin/optimize/synonyms` | M4 |
| Portal 只读问答 | `/portal/project/[token]` | §12.2 |

---

## 8. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | 2026-08-07 | KB standard Admin/Workspace 首版 |
