# 售前问答助手：从「给建议」到「直出成品」改造 Spec

## 背景

产品定位是 **花生ONE 售前问答助手**（面向展厅 + 文旅行业的售前 AI 助手，未来 ToC 商用）。当前助手在两类场景下输出的是「指导性建议内容」而非用户能直接用的回答：

1. **画布节点对话**：用户在画布某个节点（如「企业简介」）上问"帮我补充这个节点"，AI 不直接写出成品内容，而是输出「当前节点的不足：企业名称、企业性质、主营业务……建议的填写方向……」——即**教用户怎么写**，而不是**替用户写好**。
2. **全局问答**：用户直接问售前问题，AI 倾向于「建议下一步操作 / 推荐使用技能卡片」式顾问口吻，而非直接回答。

根因已定位：

- 节点对话 `_handle_node_edit` 的 system prompt（[`conversation_service.py:1398-1407`](../../apps/api/app/services/conversation_service.py#L1398-L1407)）**明确要求**「输出修改建议，不要直接给出最终 JSON」「指出当前内容的不足、给出补充或改写方向」。这是当初刻意做的「AI 建议 → 用户手动应用」设计（docstring [`conversation_service.py:1353-1358`](../../apps/api/app/services/conversation_service.py#L1353-L1358)），节点对话还**不写库**，纯靠用户看完后手动编辑。
- 全局问答 `_CONVERSATION_SYSTEM_PROMPT`（[`conversation_service.py:22-38`](../../apps/api/app/services/conversation_service.py#L22-L38)）含「建议下一步操作」「推荐用户使用技能卡片」「有建设性」等顾问口吻，叠加 `GLOBAL_CAPABILITY_CONSTRAINT` 倾向把用户引向 Skill。
- 意图识别把 `conversational` 定义为「闲聊、追问、解释、**修改建议**」（[`react_intent.py:41`](../../apps/api/app/services/react_intent.py#L41)、[`intent_service.py:191`](../../apps/api/app/services/intent_service.py#L191)），导致任何不明确触发 Skill 的问题都按「建议」口径回答。
- 节点对话和全局问答**都没有联网**——`web_search` 仅在首条消息触发的自动填充（`_handle_auto_fill`）里被调用一次，且 query 是用户原文透传。

值得对照的是：画布自动填充管线 [`canvas_agent_orchestrator.py`](../../apps/api/app/services/canvas_agent_orchestrator.py) **已经做对了**——它的 prompt 明确禁止「建议/应该/可以」措辞、只产出成品售前文案，并写进了测试断言（[`test_canvas_orchestrator.py:235`](../../apps/api/app/tests/test_canvas_orchestrator.py#L235)）。本改造大量借鉴这套已验证的写法。

## 目标

把助手从「被固定流程框死的内部工具」改造成「更通用、能联网、能对话的售前助手」，紧扣「售前问答助手」主题：

1. **节点对话默认直出成品**：基于已有资料 + 联网搜索，直接为该节点撰写一段可用的成品售前文案，并提供「一键采纳到节点」。
2. **缺料时才提示，且要具体**：只有关键信息确实缺失、必须用户客观提供时，才列出「为补全本节点，还需你提供：X、Y、Z（具体）」——这种具体的信息请求是合理且必要的，不属于「生硬的废话」。
3. **全局问答能搜后直接答**：去掉顾问口吻，能直接答就直接答，必要时联网搜索后回答。
4. **意图识别松绑**：让用户的各种自由提问能自然落到增强后的 conversational，而非被硬塞进 clarify 或 Skill。
5. **搜索 query 智能化**：根据节点上下文 + 用户问题动态改写搜索词，不再固定模板透传。
6. **面向 ToC**：交互更顺滑（一键采纳）、回答更直接。

## 非目标

1. **不引入 LLM tool-calling**：本次联网走「旁路预检索」（先搜 → 结果进 prompt → 再生成），不给 LLM 抽象层加 tool use。多轮深度检索留待未来。
2. **不改 Skill 路由架构**：明确要生成策划案/视觉/企业解析等结构化产物时仍走 Skill（保留可追溯、可审核）。
3. **不做全局问答的「采纳到节点」**：采纳动作仅对节点对话。
4. **不做搜索多轮 rerank**：现有简单 rerank 够用。
5. **不做 ToC 多租户/付费**：仅预留方向。
6. **不推翻现有分发架构**（node_id 短路 + intent 分发）：在现有结构上增强，不重写。

## 设计原则

- **默认直出成品**，不「教你写」。
- **缺料才提示，且要具体可操作**。
- **联网用旁路预检索**：复用 `acquire_web_context`，不改 LLM 抽象层。
- **保留 Skill 路由**，conversational 增强。
- **复用已验证模式**：`fill_canvas` 的写回范式、`visual-concept-actions` 的按钮模式、`canvas_agent_orchestrator` 的反建议 prompt。

## 期望行为

### 改动 1 · 节点对话 `_handle_node_edit` 直出成品

文件：[`conversation_service.py:1340-1433`](../../apps/api/app/services/conversation_service.py#L1340-L1433)

**当前**：纯 advisory text，不联网，不写库，system prompt 要求「给修改建议」。

**改为**：

1. **加联网预检索**：在拼 system prompt 前，用改动 5 的智能 query 调 `acquire_web_context(db, rewritten_query, max_results=5)`，web 命中作为生成依据之一（与节点已有 `extracted` 并列）。搜索失败/降级时静默继续（复用 provider 链的 degraded 行为），不阻断生成。
2. **system prompt 重写**（替换 [`conversation_service.py:1398-1407`](../../apps/api/app/services/conversation_service.py#L1398-L1407)）：
   - 角色：花生ONE 售前文案撰写助手，正在为画布上的单个节点撰写内容。
   - 硬性约束：
     1. 只为「当前节点」撰写内容，不涉及其它节点。
     2. **直接输出该节点可用的成品售前文案**，不要输出「建议这样写」「应该包含 X」式的元指导。
     3. 不得使用「建议、应该、可以提炼、需要考虑」等空泛建议措辞（借鉴 [`canvas_agent_orchestrator.py`](../../apps/api/app/services/canvas_agent_orchestrator.py) Pass 2 第 987 行约束）。
     4. **只有当关键信息确实缺失、必须用户客观提供时**，才在成品末尾以「为补全本节点，还需要你提供：」开头，列出具体缺失项（例：「营业执照上的成立时间」「主营业务的具体描述」），且每项说明为什么需要。
     5. 引用可追溯：成品中基于联网搜索的内容，在 sources 中标注；基于用户资料的标注；AI 推断的明确标「需确认」。不得编造。
     6. 若用户要的内容超出该节点范围，明确提示「这超出本节点范围，建议在全局对话处理」。
   - 上下文块：当前节点标题 + 已有 extracted/planning/pending + 信息来源 + **联网搜索命中**（新增）。
3. **SSE 新增 `node_draft` block**：在 `text_delta`（成品正文，给用户阅读）流完后，发一个结构化 chunk：
   ```json
   {"type": "node_draft", "data": {
     "planning": ["成品文案段落..."],
     "pending_questions": ["为补全本节点还需：..."],
     "sources": [{"type": "web_search|uploaded_file|ai_completed", "name": "...", "quote": "..."}]
   }}
   ```
   供前端渲染「采纳到节点」按钮。`text_delta` 与 `node_draft` 内容同源（text_delta 是可读正文，node_draft 是结构化数据，便于精确写库）。
4. **thinking 文案**：从「正在分析节点…生成针对性建议」改为「正在结合资料与联网搜索为该节点撰写内容…」。
5. **不在此处写库**：生成只产出 draft，写库由改动 2 的 adopt 接口在用户确认后执行。assistant 消息 `metadata` 仍记 `{intent: "node_edit", node_id, node_title}`，另存 `node_draft` 以便采纳时回取。

> 保留 docstring 的「单节点隔离」约束，删除「AI 建议 → 手动应用、不写库」约束（改为「AI 直出成品 → 用户一键采纳」）。

### 改动 2 · 「采纳到节点」接口 + 前端按钮

**后端**（新增接口，建议放 [`routers/canvas.py`](../../apps/api/app/routers/canvas.py)）：

- `POST /api/v1/projects/{project_id}/canvas/nodes/{node_id}/adopt`
- body：`{"content": {"planning": [...], "pending_questions": [...], "extracted"?: [...]}, "sources"?: [...]}`
- 逻辑（**照抄 [`fill_canvas`](../../apps/api/app/services/canvas_agent_orchestrator.py#L929-L956) 写回范式**）：
  1. `get_node` + 校验 version `is_current`（复用 [`update_node`](../../apps/api/app/services/canvas_service.py#L578-L611) 内置校验）。
  2. 合并 content：保留旧 `ui_suggestion`、`extracted`（除非 body 显式提供），用 body 的 `planning`/`pending_questions` 覆盖。
  3. `update_node(content=合并后, status="filled")`。
  4. `db.add(NodeSource(source_type="ai_completed", source_name="对话采纳", confidence="medium", quote=planning[0] if planning else None))`（planning 为空时 quote 传 None，不报错）；若 sources 含 web_search 类型，额外追加对应 NodeSource。
  5. `await db.commit()`（router 层 commit，参照 `visual-concept-actions`）。
  6. return 更新后的 node。
- 鉴权：复用现有 canvas router 的项目归属校验。

**前端**：

- [`chat-api.ts:103-165`](../../apps/web/lib/chat-api.ts#L103-L165) 的 SSE 解析新增识别 `node_draft` 类型，作为非标准 block 透传给 hook。
- [`conversation-panel.tsx`](../../apps/web/components/canvas/conversation-panel.tsx) 在节点对话的 assistant 回复下方渲染成品预览 + 「采纳到节点」按钮；点击调 adopt 接口；成功后刷新该节点（触发画布重载，参照现有节点保存后的刷新逻辑）。
- 新增 [`canvas-api.ts`](../../apps/web/lib/canvas-api.ts) 的 `adoptNode` client 方法，复用 `visual-concept-api.ts` 的封装范式。
- 采纳成功 UX：按钮置灰 → 成功 toast「已采纳到节点」→ 节点内容刷新；失败 toast 提示重试。

### 改动 3 · 全局问答 `_handle_conversational` 增强

文件：[`conversation_service.py:22-38`](../../apps/api/app/services/conversation_service.py#L22-L38)（`_CONVERSATION_SYSTEM_PROMPT`）+ `_handle_conversational` 实现。

**改为**：

1. **system prompt 重写**：
   - 去掉「建议下一步操作」「推荐用户使用技能卡片」「有建设性」。
   - 改为「能直接回答就直接回答；缺关键信息时明确问用户要具体内容（场地面积、屏幕尺寸、预算、工期等）；不要用『建议你考虑…』『你可以去…』式空话」。
   - 保留 `GLOBAL_CAPABILITY_CONSTRAINT`（防编造系统能力、防承诺不存在产物）。
2. **加搜后直答**：`_handle_conversational` 在调 LLM 前加轻量判断——用户消息是否「寒暄/极短/无信息需求」（复用现有 `_is_social_greeting` 判断或类似），若是则不搜；否则用改动 5 的智能 query 调 `acquire_web_context`，web 命中进 system prompt 上下文，LLM 基于资料 + 搜索直接答。
3. 回答中基于搜索的内容标注来源（可复用 `[ref_doc:]` 之类机制或简单行内标注）。

### 改动 4 · 意图识别松绑

文件：[`react_intent.py:41`](../../apps/api/app/services/react_intent.py#L41) + [`intent_service.py:191`](../../apps/api/app/services/intent_service.py#L191)。

- `conversational` 定义去掉「修改建议」，改为「问答、咨询、解释、闲聊、追问、各类自由提问」。
- Skill 触发条件不变（明确要生成策划案/视觉/企业解析等仍优先走 Skill，分发顺序不变，Skill 优先于 conversational）。
- 兜底仍落到 conversational（已增强）。

### 改动 5 · 搜索 query 智能化

文件：[`search_helper.py`](../../apps/api/app/services/search_helper.py) `acquire_web_context`。

- 新增 `rewrite` 能力：调用方传 `context_hint`（节点标题/类型 + 用户问题 + 已有资料摘要），`acquire_web_context` 内部用一次**短 LLM 调用（快模型/低 temperature）**把 context_hint 改写成 1-3 个高质量搜索词，再喂给现有 provider 链。
- 改写失败时降级为透传用户原文（与现状一致）。
- 节点对话传 context_hint = 节点标题 + 用户消息 + extracted 摘要；全局问答传 context_hint = 用户消息 + 项目背景摘要。
- 复用现有 Tavily → LLM-native → degraded provider 链，不改 provider。

## 完整链路（节点对话为例）

```
用户:"帮我补充企业简介节点"
 → node_id 短路 → _handle_node_edit
 → 读节点 content(extracted/planning/pending)
 → 改动5: 智能改写 query(节点上下文+用户问题)
 → acquire_web_context 联网搜(degraded 容错)
 → 改动1: 拼 system prompt(已有资料+web命中+直出成品指令)
 → LLM 流式生成成品 + (必要时)缺料提示
 → SSE: thinking_delta + text_delta(成品正文) + node_draft block(结构化)
 → 改动2: 前端渲染成品 +「采纳到节点」按钮
 → 用户点采纳 → POST /adopt
 → update_node(status=filled) + NodeSource → commit → 画布刷新
```

## 数据 / 接口变更

- **无新表**：复用 `CanvasNode.content`（形状不变：`{extracted, planning, ui_suggestion, pending_questions}`）、`NodeSource`、`update_node`。
- **新接口**：`POST /projects/{pid}/canvas/nodes/{node_id}/adopt`。
- **新 SSE block 类型**：`node_draft`。
- **`acquire_web_context` 新增参数**：`context_hint`（可选，用于 query 改写）。
- **prompt 常量变更**：`_handle_node_edit` 内 system prompt、`_CONVERSATION_SYSTEM_PROMPT`、`conversational` 意图定义文案。

## 测试计划

### 后端（pytest）

1. **节点对话直出成品**：mock LLM，断言 `_handle_node_edit` 的 system prompt 不含「输出修改建议」「指出不足」，断言生成回复是成品正文、不含「建议/应该/可以」（照搬 [`test_canvas_orchestrator.py:235`](../../apps/api/app/tests/test_canvas_orchestrator.py#L235) 断言写法）。
2. **节点对话联网**：mock `acquire_web_context`，断言 web 命中进了 system prompt 上下文；断言搜索降级时不阻断生成。
3. **node_draft block**：断言 SSE 流末尾发出结构化 `node_draft`，字段齐全。
4. **adopt 接口**：断言 content 合并正确（旧 ui_suggestion 保留）、status=filled、NodeSource 写入、is_current 校验生效（历史版本拒绝）、quote 取自 planning[0]。
5. **全局问答搜后直答**：mock 搜索，断言 conversational 路径调了 `acquire_web_context` 且结果进上下文；断言寒暄消息不触发搜索。
6. **全局问答 prompt**：断言新 prompt 不含「推荐用户使用技能卡片」「建议下一步操作」。
7. **意图松绑**：构造若干自由提问（「裸眼3D 和 LED 媒体立面有什么区别？」「这种屏幕一般多厚？」），断言落到 conversational 而非 clarify。
8. **query 智能化**：mock 改写 LLM，断言传入 provider 链的 query 是改写后的、且 context_hint 被正确利用；改写失败时降级透传原文。

### 前端（人工 + 基础检查）

- 节点对话：AI 回复下方出现成品预览 + 「采纳到节点」按钮；点击后节点内容刷新、status 变 filled。
- 全局问答：问售前问题得到直接回答（非「建议你去用 XX 技能」）。
- 类型检查 + lint 通过。

## 风险与缓解

1. **延迟增加**：节点对话/问答多一次搜索 + query 改写 LLM 调用。
   - 缓解：改写用快模型短调用；搜索链已有超时降级；寒暄/极短消息跳过搜索。
2. **采纳覆盖用户已编辑内容**：adopt 直接改画布。
   - 缓解：照抄 fill_canvas「保留旧 ui_suggestion、merge 不盲覆盖」+ NodeSource 溯源；采纳前前端展示成品预览供用户确认；is_current 版本校验。
3. **conversational 万能化吞掉 Skill 请求**。
   - 缓解：Skill 触发条件保持明确（关键词/意图），分发顺序 Skill 优先于 conversational，不变。
4. **联网搜索稳定性**：Tavily 不可用等。
   - 缓解：复用现有 provider 链 degraded 行为，搜索失败不阻断生成（退化为仅基于已有资料）。

## 验收标准

1. 在画布节点上问"帮我补充 XX"，AI 直接给出成品文案，不再出现「当前节点的不足 / 建议的填写方向」式元指导。
2. 成品下方有「采纳到节点」按钮，点击后节点内容更新、status=filled、有溯源记录。
3. 节点缺关键资料时，AI 在成品末尾列出具体的「还需你提供：X、Y、Z」。
4. 节点对话和全局问答都能联网搜索补料/回答。
5. 全局问答直接回答售前问题，不再以「建议你去用 XX 技能」收尾。
6. 自由提问（非明确 skill 触发）落到 conversational 并得到直接回答。
7. 后端测试全绿，前端类型检查 + lint 通过。
