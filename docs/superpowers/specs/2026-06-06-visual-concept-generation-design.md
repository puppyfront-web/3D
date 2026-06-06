# 视觉概念图生成工作流设计文档

> 日期：2026-06-06
> 状态：已评审
> 架构方案：Conversation-Driven Agent（方案 A）

---

## 1. 概述

### 1.1 目标

在现有对话系统中实现一个完整的视觉概念图生成工作流，支持：

- 用户输入自然语言需求
- Agent 分析需求，缺失时追问 1-3 个关键问题
- 生成视觉策划方向
- 生成 Prompt 并调用图片生成模型
- 输出概念图供用户查看
- 用户对话式修改，系统重新走完整链路生成
- 过程产物全量保存，支持回顾、对比、回滚和分支

### 1.2 设计原则

1. **不追求效率，追求质量**：每次修改都走 PLANNING → PROMPTING → GENERATING 完整链路，确保视觉策略整体自洽
2. **全量记录，可追溯**：每个版本的每个阶段产物都完整保存
3. **复用现有系统**：基于现有 Chat + Skill Runtime + SSE 流式 + RAG 检索构建，不另起炉灶
4. **对话入口**：用户从现有 Chat 页面进入，无需创建项目即可使用

### 1.3 核心决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 入口形态 | Chat 对话页 | 符合 CLAUDE.md「对话入口 + 技能路由」原则 |
| 追问方式 | 对话式追问 | 体验流畅，Agent 解析自由回答 |
| 修改方式 | 增量修改走全链路 | 视觉是整体系统，局部修改 Prompt 可能产出不协调的图片 |
| 项目关联 | 可选关联 | 降低使用门槛，后续可保存到项目 |
| 回滚/分支 | 完整对话树 | 支持多方向探索和历史回退 |
| 架构方案 | Conversation-Driven Agent | 最大化复用现有对话系统 |

---

## 2. 整体架构

### 2.1 与现有系统的集成

```
现有 ConversationService
  ↓ 增强意图识别
  "我想做一个裸眼3D的LED幕墙" → intent: "visual_concept"
  ↓ 路由
  VisualConceptAgent（新增）
  ├── 复用 VisualPromptSkill
  ├── 复用 ImageGenerationSkill
  ├── 复用 CaseRetrievalSkill
  ├── 复用 RAG HybridRetriever + ContextPack
  └── 通过 SSE StreamChunk 输出富内容
```

不新增 Skill，复用现有 6 个内置 Skill。Agent 层负责编排和对话管理。

### 2.2 状态机

`VisualConceptAgent` 管理 6 状态有限状态机：

```
COLLECTING ──→ PLANNING ──→ PROMPTING ──→ GENERATING ──→ REVIEWING
  ▲              ▲                                       │  │  │  │
  │              │                         满意───────────┘  │  │  │
  │              │                         增量修改──────────┘  │  │
  │              │                         回退上一版──────────┘  │
  │              └── 全部重来────────────────────────────────────┘
  │
  └── 追问（≤3轮）
```

| 状态 | 含义 | Agent 动作 |
|------|------|-----------|
| `COLLECTING` | 收集用户需求 | 解析用户输入，提取结构化需求；判断是否需要追问 |
| `PLANNING` | 生成视觉策划方向 | RAG 检索案例 → ContextPack 组装 → LLM 生成视觉策略 |
| `PROMPTING` | 生成 Prompt | 调用 `VisualPromptSkill` 生成正向/负向 Prompt |
| `GENERATING` | 调用图片生成 | 调用 `ImageGenerationSkill` 生成概念图 → LLM 质量自检 |
| `REVIEWING` | 等待用户反馈 | 展示图片 + 自检报告 + 操作按钮，等待用户决策 |
| `COMPLETED` | 流程结束 | 用户满意，可选保存到项目 |

所有修改路径都经过 PLANNING → PROMPTING → GENERATING 完整链路，确保质量。

---

## 3. 后端设计

### 3.1 新增文件

```
apps/api/app/agents/visual_concept.py     # VisualConceptAgent 核心
```

### 3.2 数据模型

#### VisualConceptContext

Agent 持有的对话上下文，序列化存储在 `Message.metadata_json` 中。

```python
class VisualConceptContext:
    """Agent 持有的对话上下文，序列化存储在 Message.metadata_json 中"""
    state: Literal[
        "COLLECTING", "PLANNING", "PROMPTING",
        "GENERATING", "REVIEWING", "COMPLETED"
    ]

    # 收集到的结构化需求
    requirement: VisualRequirement

    # 追问控制
    ask_round: int = 0
    max_ask_rounds: int = 3
    missing_info: list[str] = []

    # 版本树
    version_tree: VersionTree

    # 当前活跃节点 ID
    current_node_id: str | None = None

    # 当前活跃分支 ID
    current_branch_id: str = "main"
```

#### VisualRequirement

从用户自然语言中提取的结构化需求。

```python
class VisualRequirement:
    """从用户自然语言中提取的结构化需求"""
    raw_input: str                          # 用户原始输入
    scene: str | None                       # 使用场景（商场/品牌发布/地标...）
    screen_type: str | None                 # 屏幕类型（裸眼3D/LED幕墙/数字视觉...）
    brand_or_theme: str | None              # 品牌或主题
    visual_style: str | None               # 视觉风格偏好（科技/赛博朋克/国潮...）
    color_tone: str | None                  # 色调偏好
    target_audience: str | None             # 目标受众
    key_elements: list[str] = []            # 关键视觉元素
    constraints: str | None                 # 约束条件
    reference_case_ids: list[str] = []      # RAG 检索到的参考案例 ID
    modification_log: list[ModificationEntry] = []  # 修改追踪
```

#### ModificationEntry

```python
class ModificationEntry:
    """修改追踪条目"""
    round: int                    # 第几轮修改
    user_instruction: str         # 用户原始修改指令
    parsed_changes: dict          # 结构化解析结果
    previous_requirement: dict    # 修改前的需求快照（可回溯）
```

#### VersionTree

对话版本树，支持分支和回滚。

```python
class VersionTree:
    """对话版本树"""
    nodes: dict[str, VersionNode]       # node_id → VersionNode
    root_id: str                        # 根节点 ID
    active_branch: str                  # 当前活跃分支 ID
    branches: dict[str, BranchMeta]     # branch_id → 分支元信息
```

#### VersionNode

版本树中的一个节点，包含该版本的完整产物。

```python
class VersionNode:
    """版本树中的一个节点"""
    node_id: str                        # 节点唯一 ID
    parent_id: str | None               # 父节点 ID（根节点为 None）
    branch_id: str                      # 所属分支 ID
    version_label: str                  # 显示标签："V1"/"V2"/"V2'"

    # 该节点的完整产物
    requirement_snapshot: dict             # 需求快照
    visual_strategy: dict | None           # PLANNING 产物
    positive_prompt: str | None            # PROMPTING 产物
    negative_prompt: str | None            # PROMPTING 产物
    prompt_template_used: str | None       # 使用的 Prompt 模板来源
    image_url: str | None                  # GENERATING 产物
    image_metadata: dict | None            # 图片尺寸/模型/参数等
    quality_check: dict | None             # 自检报告
    rag_citations: list[dict]              # 引用来源（案例/文档/chunk）

    # 节点状态
    status: Literal["completed", "active", "abandoned"]
    children_ids: list[str]             # 子节点列表

    # 触发来源
    trigger: Literal["initial", "modify", "branch", "rollback"]
    user_instruction: str | None        # 用户的修改指令（如有）

    # 时间戳
    created_at: str
    completed_at: str | None
```

#### BranchMeta

```python
class BranchMeta:
    """分支元信息"""
    branch_id: str
    branch_name: str                    # 分支名称，如"主线"/"风格探索"/"色彩方案B"
    root_node_id: str                   # 分支起始节点
    current_node_id: str                # 分支当前节点
    status: Literal["active", "merged", "abandoned"]
    created_at: str
```

### 3.3 状态转换逻辑

| 方法 | 触发 | 输入 | 输出 | 下一状态 |
|------|------|------|------|---------|
| `handle_collecting()` | 用户每条消息 | 用户自然语言 | 追问文本 或 触发策划 | `COLLECTING` 或 `PLANNING` |
| `handle_planning()` | 自动（收集完成） | VisualRequirement | 视觉策略描述 | `PROMPTING` |
| `handle_prompting()` | 自动（策略生成完成） | 策略 + 需求 | 正/负向 Prompt | `GENERATING` |
| `handle_generating()` | 自动（Prompt 生成完成） | Prompt | 图片 URL + 自检报告 | `REVIEWING` |
| `handle_reviewing()` | 用户消息 | "满意"/"修改xxx"/"重来"/"回退" | 保存 或 调整 | `COMPLETED` / `PLANNING` / `COLLECTING` |

COLLECTING 最多追问 3 轮，超过后用已有信息 + 标记 `missing_info` 继续推进。

### 3.4 分支与回滚操作

```python
# 1. 回滚
async def handle_rollback(target_node_id: str, ctx: VisualConceptContext):
    """
    - 该节点之后的所有节点标记为 abandoned（保留，不删除）
    - 从该节点的 requirement_snapshot 恢复 VisualRequirement
    - 用户下一次输入从这里继续
    """

# 2. 分支
async def handle_branch(from_node_id: str, branch_name: str, ctx: VisualConceptContext):
    """
    - 原分支不受影响，继续独立
    - 新分支从 from_node 复制 requirement_snapshot 作为起点
    - 切换 active_branch 到新分支
    - 用户下一次输入进入新分支的 COLLECTING 状态
    """

# 3. 切换分支
async def handle_switch_branch(branch_id: str, ctx: VisualConceptContext):
    """
    - 恢复该分支 current_node 的完整上下文
    - 继续该分支的迭代
    """
```

### 3.5 与 ConversationService 的集成

修改 `ConversationService._process_message()` 路由逻辑：

```python
async def _process_message(self, ...):
    intent = await self.intent_detector.detect(user_input, history)

    if intent.intent_type == "run_skill":
        # 现有：直接执行 Skill
        ...

    # 新增：视觉概念图意图路由
    elif intent.intent_type == "visual_concept":
        ctx = self._load_or_create_visual_concept_ctx(conversation)
        async for chunk in self.visual_concept_agent.handle_message(user_input, ctx):
            yield chunk
        self._save_visual_concept_ctx(conversation, ctx)

    else:
        # 现有：普通对话
        ...
```

上下文持久化：`VisualConceptContext` 序列化为 JSON，存储在 `Message.metadata_json` 字段中。每轮对话保存一次，重启后可恢复。

### 3.6 SSE 输出的富内容块

利用现有 `StreamChunk` + `ContentBlock` 体系：

| 阶段 | 输出块 | 说明 |
|------|--------|------|
| COLLECTING（追问） | `text_delta` | LLM 生成的追问文本 |
| COLLECTING（追问） | `action_buttons` | 快捷回复建议 |
| PLANNING | `text_delta` | 视觉策略描述文本 |
| PLANNING | `visual_strategy`（新增） | 视觉策略结构化摘要 |
| PLANNING | `skill_progress` | RAG 检索进度 |
| PROMPTING | `text_delta` | 显示生成的 Prompt |
| PROMPTING | `artifact` | Prompt 文本（可复制） |
| GENERATING | `skill_progress` | 图片生成进度 |
| GENERATING | `visual_result` | 概念图展示 |
| GENERATING | `quality_check`（新增） | AI 自检报告 |
| REVIEWING | `action_buttons` | "满意" / "修改" / "重来" / "回退" |
| COMPLETED | `artifact` | 最终产物汇总 |

### 3.7 新增 ContentBlock 类型

在现有 `ContentBlock` schema 中新增两种块类型：

1. **`visual_strategy`**：展示视觉策划方向，包含风格、色调、构图、核心元素、参考案例、来源追溯
2. **`quality_check`**：展示 AI 自检报告，包含每项需求的匹配状态和待确认项

### 3.8 新增 API 端点

```python
# 产物树相关 API
GET  /api/v1/conversations/{id}/artifacts
# 返回该对话所有版本的完整产物列表

GET  /api/v1/conversations/{id}/artifacts/{node_id}
# 返回指定节点（版本）的详细产物，node_id 为 VersionNode 的 UUID

GET  /api/v1/conversations/{id}/artifacts/compare?node_a={id}&node_b={id}
# 返回两个节点的对比数据，支持跨分支对比

GET  /api/v1/conversations/{id}/version-tree
# 返回完整版本树结构（节点、分支、关系）

POST /api/v1/conversations/{id}/actions
# 统一动作端点：
#   { "action_type": "rollback", "target_node_id": "..." }
#   { "action_type": "branch", "from_node_id": "...", "branch_name": "风格探索" }
#   { "action_type": "switch_branch", "branch_id": "..." }
#   { "action_type": "rename_branch", "branch_id": "...", "new_name": "..." }
#   { "action_type": "abandon_branch", "branch_id": "..." }
```

数据来源为 `Message.metadata_json` 中的 `VisualConceptContext`，不需要额外数据表。

---

## 4. RAG 集成

### 4.1 两次 RAG 介入

**第一次：COLLECTING 阶段——辅助追问**

```
用户说"我想做一个裸眼3D"
  → 初步 RAG 检索（轻量）
  → 检索到相似案例的 screen_type / scene / visual_style 分布
  → 帮助 Agent 判断缺失信息
  → 生成精准追问
```

**第二次：PLANNING 阶段——驱动视觉策略**

```
完整的 VisualRequirement 已收集
  → 深度 RAG 检索
    ├── HybridRetriever 向量检索
    ├── 案例表直接查询（按 scene / screen_type / visual_style 过滤）
    ├── Prompt 模板库检索（按 task_type="visual" + style 匹配）
    └── 技术规则检索（按 screen_type 过滤）
  → ContextPack 组装
    ├── 匹配案例 top 3-5
    ├── 相关文档 chunk
    ├── 推荐的 Prompt 模板
    ├── 适用的技术规则
    └── 缺失信息标记
  → LLM 基于 ContextPack 生成视觉策略
  → 策略中包含参考案例引用 + 技术约束提示
```

### 4.2 引用追溯

每次 PLANNING 的 RAG 检索结果都记录到 `VersionNode.rag_citations`：

```python
rag_citations: [
    { type: "case", id: "A012", title: "某汽车品牌裸眼3D发布", score: 0.92 },
    { type: "document_chunk", id: "ch_345", document_id: "doc_12", section: "视觉策略" },
    { type: "prompt_template", id: "tpl_08", name: "赛博科技风视觉Prompt" },
    { type: "technical_rule", id: "rule_05", title: "裸眼3D屏幕分辨率要求" },
]
```

---

## 5. 前端设计

### 5.1 新增前端文件

```
apps/web/
├── lib/
│   ├── visual-concept-context.tsx      # 视觉概念图会话状态管理
│   └── visual-concept-api.ts           # 产物查询 API 客户端
│
├── components/chat/blocks/
│   ├── visual-strategy-card.tsx        # 视觉策略展示卡片
│   ├── quality-check-card.tsx          # AI 自检报告卡片
│   ├── revision-history.tsx            # 修改历史时间线
│   ├── version-tree-panel.tsx          # 版本树面板
│   ├── version-node-card.tsx           # 单个版本节点卡片
│   ├── branch-switcher.tsx             # 分支切换标签栏
│   ├── version-compare-view.tsx        # 两版本对比
│   ├── branch-dialog.tsx              # 新建分支/重命名弹窗
│   └── artifact-detail-modal.tsx       # 单个产物详情弹窗
```

### 5.2 不新增页面

完全复用现有 `/workspace/chat` 页面。增强方式：

- `ChatProvider` 的 `sendMessage` 无需改动——已走 SSE 流式 + 意图路由
- `message-bubble.tsx` 的富内容渲染增加 `visual_strategy`、`quality_check` 两种新块类型
- 新增 `VisualConceptProvider` 作为 `ChatProvider` 的增强层，管理版本树和产物状态

### 5.3 前端状态管理

```typescript
interface VisualConceptState {
  isActive: boolean;                    // 当前对话是否处于视觉概念图模式
  agentState: AgentState;               // 状态机当前状态
  requirement: VisualRequirement | null; // 结构化需求
  versionTree: VersionTree | null;       // 版本树
  currentBranchId: string;              // 当前分支
  currentNodeId: string | null;         // 当前节点
  currentImageUrl: string | null;       // 当前概念图
  qualityCheck: QualityReport | null;   // 最新自检报告
}
```

数据流：后端 SSE 推送 `content_block_data` → 前端解析块类型 → 更新 `VisualConceptState` → 触发对应卡片渲染。

### 5.4 各状态下的前端展示

#### COLLECTING（追问）

- 助手消息：追问文本 + 编号的缺失信息列表
- 底部：`action_buttons` 快捷建议芯片

#### PLANNING（视觉策略）

- `skill_progress`：RAG 检索进度
- `visual_strategy_card`：风格、色调、构图、核心元素、参考案例、来源追溯
- 文本：策略描述

#### PROMPTING → GENERATING

- `skill_progress`：生成进度条
- `artifact`：Prompt 文本（可复制）
- `visual_result`：概念图展示

#### REVIEWING

- `visual_result`：概念图
- `quality_check_card`：AI 自检报告（✅/⚠️ 状态）
- `revision_history`：修改历史（可折叠，从 V2 起显示）
- `action_buttons`：满意 / 修改 / 重来 / 回退

### 5.5 过程产物面板

右侧可展开面板，支持：

| 操作 | 说明 |
|------|------|
| 按版本浏览 | 点击 V1/V2 切换，展开查看该版本所有阶段产物 |
| 按分支浏览 | 切换分支标签，查看不同探索方向 |
| 查看单个产物 | 点击产物卡片，弹窗显示完整内容 |
| 图片放大 | 全屏查看 + 下载原图 |
| Prompt 复制 | 一键复制正向/负向 Prompt |
| 引用追溯 | 查看该版本使用的案例/文档/chunk |
| 版本对比 | 选择两个版本，左右对比差异（需求 diff + 策略 diff + 图片并排） |
| 回退到某版 | 以该版需求为起点重新生成 |
| 新建分支 | 从任意版本创建新探索路径 |
| 追问回顾 | 查看所有追问 Q&A 记录 |

---

## 6. 质量保障

### 6.1 生成全链路质量检查

```
COLLECTING
  └─ 结构化需求校验（必须包含 scene 或 screen_type 之一）

PLANNING
  └─ 策略必须包含：风格、色调、构图、核心元素
  └─ 引用案例数 ≥ 1（有检索结果时）
  └─ 缺失信息必须标注

PROMPTING
  └─ Prompt 长度校验（正向 50-500 字符，负向 0-300 字符）
  └─ 禁止词检查
  └─ 必须与策略一致（LLM 自检）

GENERATING
  └─ 图片生成后 LLM 质量自检（对照 requirement 逐项检查）
  └─ 自检结果包含：每项需求的匹配状态 + 待确认项

REVIEWING
  └─ 保存前检查：产物完整性（策略 + Prompt + 图片 + 自检 + 引用）
  └─ 关联项目时：写入 generation_outputs 表，可追溯
```

### 6.2 异常处理

| 异常场景 | 处理策略 | 用户感知 |
|---|---|---|
| LLM 生成策略失败 | 重试 1 次，仍失败则告知并提供重试按钮 | "策略生成遇到问题，请点击重试" |
| LLM 生成 Prompt 失败 | 同上 | 同上 |
| 图片生成服务超时/失败 | 重试 1 次，仍失败则保留 Prompt，告知可稍后重试 | "图片生成暂时不可用，Prompt 已保存" |
| RAG 检索无结果 | 不阻塞，策略中标注"未检索到相似案例，策略基于通用经验生成" | 策略中有提示 |
| 追问轮次超过 3 轮 | 自动用已有信息 + 标记 missing_info 继续推进 | "信息已足够，缺失信息将在结果中标注" |
| 分支数量过多（>10） | 提示归并或废弃部分分支 | "分支较多，建议归并一些探索方向" |
| 版本树深度过大（>20 节点） | 提示归档早期版本 | "版本历史较长，建议归档早期版本" |
| 对话上下文超出 token 限制 | 只传最近 3 个节点完整产物 + 之前节点摘要 | 无感知 |
| 用户长时间无响应后回来 | 恢复上次状态，简要回顾进展 | "欢迎回来，上次我们在..." |

---

## 7. 意图识别增强

### 7.1 新增意图类型

在现有 `IntentDetector` 中新增 `visual_concept` 意图类型。

### 7.2 关键词匹配

```python
_VISUAL_CONCEPT_KEYWORDS = {
    "high": [
        "生成概念图", "出概念图", "视觉概念", "概念设计",
        "生成效果图", "出效果图", "视觉方案",
    ],
    "medium": [
        "裸眼3D", "LED幕墙", "媒体立面", "数字视觉",
        "视觉创意", "概念图", "创意图",
        "我想做一个", "帮我设计一个", "生成一个视觉",
    ],
}
```

### 7.3 路由规则

- 如果当前对话已有 `VisualConceptContext`（metadata_json 中存在），所有后续消息直接走 `VisualConceptAgent`
- 只有新对话的第一条消息需要意图判断
- 用户在 REVIEWING 状态下的回复（"满意"/"修改"/"重来"）不需要意图识别，直接由 Agent 处理

---

## 8. 端到端数据流

### 8.1 完整用户旅程

```
1. 用户输入："帮我做一个汽车品牌的裸眼3D概念图"
   → IntentDetector → visual_concept
   → 创建 VisualConceptContext(state=COLLECTING)
   → 轻量 RAG 检索辅助追问
   → 缺失 scene / visual_style → 追问

2. 用户回答："品牌发布会场景，科技感风格"
   → 合并到 VisualRequirement
   → 信息足够 → 创建 V1 节点
   → 自动进入 PLANNING

3. PLANNING
   → CaseRetrievalSkill → 5个匹配案例
   → ContextPack 组装
   → LLM 生成视觉策略
   → 保存到 V1.visual_strategy + rag_citations
   → 自动进入 PROMPTING

4. PROMPTING
   → VisualPromptSkill → 正/负向 Prompt
   → Prompt 质量校验
   → 保存到 V1.positive/negative_prompt
   → 自动进入 GENERATING

5. GENERATING
   → ImageGenerationSkill → 概念图
   → LLM 质量自检 → quality_check
   → 保存到 V1.image_url + quality_check
   → 进入 REVIEWING

6. 用户说："背景改成深红色，加粒子效果"
   → 解析修改意图
   → 合并修改到 VisualRequirement
   → 创建 V2 节点（parent=V1, trigger=modify）
   → 走完整链路 PLANNING → PROMPTING → GENERATING
   → 回到 REVIEWING

7. 用户满意
   → 可选关联项目，写入 generation_outputs
   → COMPLETED
```

### 8.2 分支场景

```
8. 用户在 V2 点击"从 V1 分支"→ 命名"国潮风探索"
   → 创建分支 branch_b
   → 从 V1 复制 requirement_snapshot
   → 用户输入"换成国潮风格"
   → 创建 V1'（branch=branch_b）
   → 走完整链路
   → 主线 V2 不受影响
   → 可随时切换对比
```

---

## 9. 测试策略

### 9.1 后端单元测试

| 测试模块 | 覆盖内容 |
|---|---|
| `test_visual_concept_agent.py` | 状态机转换、追问逻辑（1-3轮）、信息足够判断、修改意图解析 |
| `test_version_tree.py` | 节点创建、分支创建、回滚、分支切换、跨分支对比、废弃标记 |
| `test_visual_requirement.py` | 需求解析、字段合并、修改日志记录、快照恢复 |
| `test_intent_visual_concept.py` | 意图识别关键词命中、上下文感知路由、LLM 降级路径 |
| `test_visual_concept_api.py` | 产物查询 API、版本树 API、分支操作 API、权限校验 |

### 9.2 后端集成测试

| 场景 | 验证点 |
|---|---|
| 完整流程（mock provider） | COLLECTING→PLANNING→PROMPTING→GENERATING→REVIEWING→COMPLETED |
| 追问后生成 | 3轮追问→生成策略→验证 rag_citations 不为空 |
| 增量修改走全链路 | 修改→V2 策略/Prompt/图片都与 V1 不同→modification_log 完整 |
| 分支 + 回滚 | 创建分支→在分支生成→回滚主线→两条分支数据独立 |
| RAG 检索命中 | 构造汽车品牌案例→输入汽车需求→命中该案例 |
| RAG 无结果 | 输入冷门需求→策略中标注"无相似案例" |
| 产物 API | 版本树查询、产物详情、版本对比数据正确 |

### 9.3 前端测试重点

| 检查项 | 说明 |
|---|---|
| 追问交互 | Agent 追问后用户回答，消息正确显示，快捷按钮可点击 |
| SSE 流式渲染 | 各阶段内容块按序渲染，进度条正确，流式文字动画 |
| 概念图展示 | 图片正确加载，全屏查看，下载 |
| 产物面板 | 时间线正确展示，版本展开/折叠，单个产物查看 |
| 分支操作 | 新建分支、切换分支、分支内独立迭代 |
| 版本对比 | 选择两个版本、diff 高亮、图片并排 |
| 回滚操作 | 回滚后历史版本标记废弃、从回滚点继续生成 |
| 自检报告 | 每项状态（✅/⚠️）正确渲染 |
| 异常处理 | 生成失败时显示重试按钮，不白屏 |

---

## 10. 文件变更清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `apps/api/app/agents/visual_concept.py` | VisualConceptAgent 核心实现 |
| `apps/web/lib/visual-concept-context.tsx` | 前端状态管理 |
| `apps/web/lib/visual-concept-api.ts` | 产物查询 API 客户端 |
| `apps/web/components/chat/blocks/visual-strategy-card.tsx` | 视觉策略卡片 |
| `apps/web/components/chat/blocks/quality-check-card.tsx` | 自检报告卡片 |
| `apps/web/components/chat/blocks/revision-history.tsx` | 修改历史时间线 |
| `apps/web/components/chat/blocks/version-tree-panel.tsx` | 版本树面板 |
| `apps/web/components/chat/blocks/version-node-card.tsx` | 版本节点卡片 |
| `apps/web/components/chat/blocks/branch-switcher.tsx` | 分支切换栏 |
| `apps/web/components/chat/blocks/version-compare-view.tsx` | 版本对比 |
| `apps/web/components/chat/blocks/branch-dialog.tsx` | 分支操作弹窗 |
| `apps/web/components/chat/blocks/artifact-detail-modal.tsx` | 产物详情弹窗 |

### 修改文件

| 文件 | 修改内容 |
|------|---------|
| `apps/api/app/services/conversation_service.py` | 增加 visual_concept 意图路由 |
| `apps/api/app/services/intent_service.py` | 增加 visual_concept 意图类型和关键词 |
| `apps/api/app/schemas/conversation.py` | 增加 visual_strategy / quality_check 块类型 |
| `apps/api/app/routers/conversations.py` | 增加产物/版本树/分支操作 API |
| `apps/web/components/chat/message-bubble.tsx` | 增加新块类型渲染 |
| `apps/web/components/chat/chat-input.tsx` | 增加视觉概念图快捷入口 |
| `apps/web/types/index.ts` | 增加 VisualConcept 相关类型定义 |

---

## 11. 风险与待确认项

1. **LLM 生成质量**：视觉策略和 Prompt 的质量高度依赖 LLM 能力，mock provider 无法验证真实效果
2. **图片生成成本**：每次修改都走全链路意味着每次都调用图片生成 API，需要关注成本控制
3. **版本树数据量**：长期使用后 metadata_json 可能膨胀，需要考虑清理策略
4. **并发安全**：同一对话的分支操作如果并发可能产生冲突，需要考虑乐观锁
