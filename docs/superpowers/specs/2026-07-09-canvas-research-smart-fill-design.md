# 画布「采集 → 智能归档」设计 Spec

## 背景

承接「售前问答助手『直出成品』改造」(见 [2026-07-09-presale-assistant-direct-output-design.md](./2026-07-09-presale-assistant-direct-output-design.md))。上一轮改造让助手能联网搜资料、直出成品;但调研发现两个缺口:

1. **搜索结果对用户不可见**:`acquire_web_context` 实际返回 `(hits, summary)` 两部分(hits 带 title/url/domain/snippet/published_at/source_type/confidence;summary 带 key_points/conflicts/missing_info/recommended_usage)。但 [`_handle_conversational`](../../apps/api/app/services/conversation_service.py) 和 [`_handle_node_edit`](../../apps/api/app/services/conversation_service.py) 都**只把 hits 折叠进 system prompt 的【网络搜索命中】块,且把 summary 整个丢掉**(`web_hits, _ = ...`)。用户只能看到 LLM 流出的回答,**完全看不到搜到了什么**;summary 里的关键点/冲突/缺失信息也没用上。全仓 grep 确认:无任何 `search_results`/`web_results` SSE block。

2. **搜索内容不进画布模块**:画布现有四条写入路径——首条消息自动填充([`_handle_auto_fill`](../../apps/api/app/services/conversation_service.py))、手动重新生成(`agent-runs`)、「采纳到节点」按钮(上一轮做的)、手动编辑。其中**网络搜索结果从不进入节点 `content`**,只作为 `NodeSource` 溯源行存在;`content` 永远是 LLM 蒸馏的 `extracted`/`planning`。且除了首条/重新生成(填固定三大板块模板),没有任何路径能"基于搜索把内容归档进画布模块"。

## 目标

把助手从"搜资料只为自己回答"升级为"搜资料 → 整理可见 → 智能归档进画布模块":

1. **搜索整理结果在对话里富文本可见**:把 `acquire_web_context` 的产出整理成「按目标模块分组的要点 + 来源引用」展示给用户,不再隐形塞进 prompt。
2. **AI 智能归档到多个模块**:搜到资料后,AI 判断每条要点属于哪个模块,整理后分发到对应模块。
3. **人确认 + 版本化写回**:首条消息自动填充(可见化);后续发现新内容时,先在对话里列出、问用户,用户接受才填,每次填充做好版本管理。
4. **不与刚做的能力冲突**:节点对话的单节点 `node_draft`/adopt 保留不动;全局问答的"搜后直答"保留。

## 非目标

1. **不改节点对话的单节点 adopt**(保留上一轮成果)。
2. **不重构 `fill_canvas`**:只复用其反编造 prompt 纪律,不改其本体逻辑。
3. **不做多轮深度检索 / rerank**:现有简单检索 + 一次整理 pass 够用。
4. **不引入 LLM tool-calling**:联网继续走旁路预检索(先搜 → 结果进 prompt → 再生成),不给 LLM 抽象层加 tool use。
5. **不做 ToC 多租户 / 付费**:仅预留方向。
6. **不做搜索结果原样进模块**(raw title/snippet 直接当 content):模块内容始终是 AI 整理后的要点,raw 命中只作溯源。

## 设计原则

- **搜索整理结果默认可见**,不再隐形塞 prompt。
- **AI 负责整理 + 归属判断**,但**写回前人确认**(首条 auto 例外)。
- **复用已验证模式**:`acquire_web_context` 的搜索/降级、`fill_canvas` 的反编造 prompt 与多节点写回、`adopt_node_draft` 的合并 + NodeSource 溯源、`canvas_fill_proposal` 沿用 node_draft 的 SSE block + 前端渲染范式。
- **版本化写回**:每次采纳生成新 `CanvasVersion` 快照,可回退。

## 架构:一个引擎,三处复用

### 核心引擎 `research_and_propose`

新服务 [`apps/api/app/services/canvas_research_service.py`](../../apps/api/app/services/canvas_research_service.py):

```
research_and_propose(db, project_id, context_hint, mode) -> Proposal
  1. acquire_web_context(db, query, max_results=5, context_hint)   # 已建好:智能改写 + 搜索 + 降级
  2. 读画布模块模板(三大板块 + 各节点标题) -> "目标模块清单"
  3. 一次 LLM「整理 + 归属」pass:
     - 输入:搜索命中 + 项目/企业上下文 + 模块清单
     - 输出:按模块分组的要点 + 每条来源引用
     - 复用 fill_canvas 反编造纪律(禁「建议/应该/可以」、直出要点、标注来源、推断标「需确认」)
  4. 返回 Proposal,不写库
```

**Proposal 形状**:

```json
{
  "mode": "auto" | "ask",
  "groups": [
    {
      "module_key": "company_intro",
      "module_title": "企业简介",
      "points": ["要点1…", "要点2…"],
      "citations": [{"name": "XX百科", "url": "…", "type": "web_search"}]
    }
  ],
  "summary": {"key_points": ["…"], "missing_info": ["…"]}
}
```

### 数据流(三触发共用引擎,差别在 mode 与是否自动写)

```
① 首条消息  _handle_auto_fill
   → 引擎(mode=auto)
   → 流式 emit canvas_fill_proposal(可见化:让用户看到填了什么)
   → 自动写回(复用现有 fill_canvas 多节点写回 + 版本化)   ← 现有行为,加"可见"

② 后续问答  _handle_conversational(搜到模块相关新信息时)
   → 先正常 text_delta 直答用户问题
   → 引擎(mode=ask)
   → emit canvas_fill_proposal(询问态:不写)
   → 用户点「采纳」→ POST /fill-accept → 版本化写回

③ 节点对话  _handle_node_edit
   → 保持上一轮的单节点 node_draft / adopt 不动(不纳入本特性)
```

### 版本管理(核心要求)

`fill-accept` 写回时**创建新的 `CanvasVersion` 快照**(复用 `fill_canvas` 已有的版本创建路径——它本就版本化)。单节点 adopt 写当前版本、不新建,该行为保留原样。这样每次"采集填充"都是一个可回滚版本节点,前端版本面板可回退。

### 触发门槛(避免提案噪音)

后续问答(`_handle_conversational`)中,**只有当「整理 pass」产出了能映射到模块、且对该模块是新增信息(不重复节点已有内容)的要点时,才 emit 提案**;否则只答问题、不提案。寒暄/极短消息不进引擎。

## 组件、接口与前端

### 后端组件

| 组件 | 位置 | 职责 |
|---|---|---|
| `canvas_research_service.py`(新) | services/ | `research_and_propose()` 引擎 + `accept_fill_proposal()` 版本化写回 |
| `acquire_web_context`(复用) | search_helper.py | 搜索 + 智能改写 + 降级(已建好) |
| 反编造 prompt(复用) | 从 fill_canvas ~987 行抽成共享常量 | 整理 pass 的语气纪律 |
| `canvas_service` 版本 helper + `update_node` + `NodeSource`(复用) | canvas_service.py | 版本快照 + 合并写回 + 溯源 |
| `conversation_service.py`(改) | services/ | 引擎接进 `_handle_auto_fill`(auto/可见)和 `_handle_conversational`(ask/达标时);`_handle_node_edit` 不动 |

### 新 SSE block:`canvas_fill_proposal`

- 字段即 Proposal 形状 + `mode`。
- 前端 `chat-api.ts` 默认分支已自动收非标准 block(同 node_draft);需在 `ContentBlock.type` 联合类型加 `"canvas_fill_proposal"`。

### 新接口:`POST /api/v1/projects/{pid}/canvas/fill-accept`

- body:用户勾选的 `{groups: [{module_key, points, citations}], summary}`(客户端回传提案内容,与现有 adopt 回传 `NodeAdoptIn` 风格一致;服务端再校验项目归属 + module_key 合法)。
- 服务端:创建新 `CanvasVersion` 快照 → 对每个选中 group 找到对应节点 → 合并写回(保留旧 `ui_suggestion`/`extracted`、覆盖 `planning`/`pending`、status=filled)→ 每个 citation 追加 `NodeSource(web_search)` 溯源。
- 返回:新版本 + 更新后的节点。

### 前端 UX

- 新组件 `CanvasFillProposalBlock.tsx`:
  - `mode=auto`:渲染为「已采集填充」摘要(分组要点 + 来源),只读;可经版本面板回退。
  - `mode=ask`:分组要点 + 来源 + 每组勾选框(默认勾) + 「采纳所选」按钮。
- 接进 `conversation-panel.tsx` 的 `renderContentBlock`(同 node_draft),传 `ctx={projectId, onAccepted=loadCurrent}`。
- `canvas-api.ts` 加 `acceptFillProposal(projectId, body)`。
- 采纳 UX:按钮置灰 → toast「已采纳到画布」→ `loadCurrent()` 刷新 → block 切「已采纳」态。

### 数据 / 接口变更

- **无新表**(复用 `CanvasNode.content` / `NodeSource` / `CanvasVersion`)。
- 新 SSE block 类型 `canvas_fill_proposal` + 联合类型条目。
- 新接口 `POST /projects/{pid}/canvas/fill-accept`。
- 新 service `canvas_research_service.py`。
- 共享 prompt 常量(从 fill_canvas 抽出反编造约束)。

## 分期落地(降风险,早出价值)

- **Phase A**(先做,低风险):引擎 + `canvas_fill_proposal` block + 渲染 + **首条消息 auto 模式可见化**。交付:用户能看到 auto-fill 搜了/填了什么。
- **Phase B**:后续问答 ask 模式 + `fill-accept` 接口 + 版本化写回 + 勾选采纳 UX。交付:完整"搜到新内容 → 问你 → 接受才填 → 版本化"闭环。

两期共用引擎和 block,Phase A 是 Phase B 的子集,不返工。

## 测试计划

### 后端(pytest)

1. **引擎 `research_and_propose`**:mock 搜索 + mock 整理 LLM → 断言 Proposal 形状(groups 含 module_key/points/citations);断言要点**无「建议/应该/可以」**(照搬 [`test_canvas_orchestrator.py:235`](../../apps/api/app/tests/test_canvas_orchestrator.py#L235) 断言风格);断言 citation 带 source。
2. **引擎降级**:搜索失败 → 返回空提案、不抛异常。
3. **SSE 触发**:`_handle_auto_fill` 发 `canvas_fill_proposal`(auto);`_handle_conversational` 达标时发(ask);寒暄/无关问题不发。
4. **门槛**:mock 节点已有内容 → 断言只对"新增"信息产出 group(去重)。
5. **`fill-accept`**:创建新 `CanvasVersion`、合并正确(保留 ui_suggestion/extracted)、status=filled、每条 citation 写 `NodeSource`;非法 module_key 拒绝;项目归属校验。
6. **版本**:accept 后 is_current 指向新版本、旧版本保留(可回退)。

### 前端(人工 + 基础检查)

- 首条消息后:画布被填,且对话里能看到分组要点 + 来源的「已采集填充」摘要。
- 后续问答搜到模块新信息:出现提案(分组 + 来源 + 勾选 + 采纳);无关问题只答不提案。
- 勾选 + 采纳 → 模块内容刷新、status=filled、生成新版本可回退。
- tsc + lint 通过。

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| 延迟:引擎多一次搜索 + 整理 LLM | 整理 pass 用快模型;首条本就付这成本;后续仅在达标时跑 |
| 提案噪音(每问一句都弹) | 门槛:仅"新增 + 模块相关"才提案;可关 |
| 版本膨胀 | 即要求的版本管理,版本面板已支持回退 |
| 整理 LLM 把要点归错模块 | ask 模式用户采纳前可审;auto(首条)是已接受既有风险 |
| 复用 fill_canvas prompt 有风险 | 只复用约束文案(抽成共享常量),不重构 fill_canvas 本体 |

## 验收标准

1. 首条消息后画布被填,且对话里可见「采集了什么、填进哪些模块」的分组要点 + 来源。
2. 后续问答搜到模块相关新信息 → 出现提案(分组 + 来源 + 勾选 + 采纳);无关问题只答不提案。
3. 勾选 + 采纳 → 模块内容更新、status=filled、有 NodeSource 溯源、生成新版本(可回退)。
4. ask 模式绝不自动写库;只有首条 auto 和用户采纳才写。
5. 搜索/LLM 失败 → 对话照常直答,不阻断、不报错。
6. 后端测试全绿;前端 tsc + lint 通过。

## 实现待定项(写 plan 时落实,不影响设计方向)

1. **模块引用方式**:`Proposal.group.module_key` 需能映射到具体 `CanvasNode`。需确认 `CanvasNode` 是否有稳定 `key` 字段;若有则用 key,若无则按 group+title 定位或补一个稳定标识。plan 第一步核实 [`models/canvas.py`](../../apps/api/app/models/canvas.py)。
2. **`context_hint` 来源**:auto 模式 = 用户首条消息;ask 模式 = 用户当前问题 + 项目/企业背景摘要。搜索 query 复用上一轮 Task 1 的智能改写。
3. **整理 pass 模型**:用快模型 / 低 temperature(plan 按项目 Model Gateway 配置落实具体 provider)。
4. **版本创建 helper**:复用 `fill_canvas` 现有的版本创建/`is_current` 翻转逻辑,plan 落实精确函数(优先抽成 `canvas_service` 上的可复用 helper)。

## 与上一轮改造的关系

| 上一轮(直出成品) | 本轮(采集 → 智能归档) |
|---|---|
| 节点对话直出成品 + 单节点 adopt | 不动(保留) |
| 全局问答搜后直答 | 保留直答,达标时**追加**采集提案 |
| 搜索隐形进 prompt | 搜索整理结果**可见** + 归档进画布 |
| 单节点写回 | **多模块**写回 + 版本化 |
