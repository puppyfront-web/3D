# SOP Pipeline 设计文档：对话流驱动的端到端方案管线

> 日期: 2026-06-09
> 状态: 已确认
> 模式: 方案 A — 对话流驱动，单条管线先跑通

---

## 1. 目标

用户输入一句话（如"给华为设计一套3D幕墙方案"），系统能够：

1. 自动检测缺失信息 → 要求补充
2. 信息齐备后逐步执行：企业解析 → 策划案 → 视觉方案 → 导出
3. 关键节点暂停，用户可确认或微调
4. 最终输出效果图 + 方案文档

MVP 阶段只做一条标准管线，后续再扩展为 SOP 引擎。

---

## 2. 设计决策记录

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 执行模式 | 半自动：自动推进 + 关键节点人工确认 | 平衡效率与质量 |
| 暂停粒度 | 关键节点暂停（2-3 次） | 4 个 Skill 中 3 个暂停，视觉生成后自动导出 |
| 微调方式 | 卡片编辑 + 对话微调双入口 | 灵活性高，卡片提供结构化操作，对话兜底 |
| 实现范围 | 单条管线先跑通 | MVP 最小可用，验证核心流程 |
| 架构方案 | 方案 A：对话流驱动 | 复用现有 conversation SSE 流，实现量最小 |

---

## 3. Pipeline 阶段定义

```
Stage 1: company_analysis（企业解析）
─────────────────────────────────────
输入: 用户消息中提取的企业信息 + 项目需求
输出: 企业画像卡片 (company_analysis_card) + action_buttons
暂停: ✅ 等待用户确认企业画像
确认: action:confirm → 推进到 Stage 2
微调: 用户输入修改意见 → 重新执行 Stage 1

Stage 2: proposal_generation（策划案生成）
─────────────────────────────────────
输入: Stage 1 确认的企业画像 + 项目需求 + RAG 检索
输出: 策划案 markdown + proposal_section 卡片 + action_buttons
暂停: ✅ 等待用户确认策划案
确认: action:confirm → 推进到 Stage 3
微调: 用户输入如"第三章改一下" → 重新生成

Stage 3: visual_prompt + image_generation（视觉方案）
─────────────────────────────────────
输入: Stage 2 确认的策划案 + 视觉方向
输出: 视觉策略卡片 + 2 张效果图 (visual_result) + action_buttons
暂停: ✅ 等待用户选择版本/反馈
确认: "用第一张"/"继续" → 推进到 Stage 4
微调: "色调再冷一点" → 重新生成

Stage 4: export（导出）
─────────────────────────────────────
输入: 前面所有确认的产物
输出: artifact 卡片（Word/PPT 下载链接）
暂停: ❌ 不暂停，直接导出
```

---

## 4. 意图识别与路由

### 4.1 新增意图: `sop_pipeline`

在 `intent_service.py` 的 `_keyword_match()` 中新增关键词匹配：

```python
_PIPELINE_KEYWORDS = {
    "high": [
        "设计一套3D幕墙方案", "做一套完整方案", "从零开始做方案",
        "端到端方案", "全流程", "从头到尾做",
    ],
    "medium": [
        "完整方案", "全套方案", "帮我设计方案",
        "3D幕墙方案", "LED方案设计",
    ],
}
```

**触发条件**：
- 匹配关键词 + 消息中包含实体信息（公司名/行业/需求） → `intent: sop_pipeline, confidence: 0.8`
- 匹配关键词但无实体 → `intent: sop_pipeline_needs_info, confidence: 0.9` → 立即返回要求补充

### 4.2 路由分支

`conversation_service.py` 的 `process_message_stream()` 新增：

```python
# 检查是否有暂停中的 pipeline 需要恢复
pipeline_state = self._load_pipeline_state(conv)
if pipeline_state and pipeline_state.get("status") == "paused":
    async for chunk in self._handle_sop_pipeline_resume(
        db, conv_uuid, user_message, pipeline_state, history
    ):
        yield chunk
    return

# 新增路由
if intent.intent == "sop_pipeline":
    async for chunk in self._handle_sop_pipeline(
        db, conv_uuid, user_message, intent, history
    ):
        yield chunk
elif intent.intent == "sop_pipeline_needs_info":
    # 快速响应，不走 LLM
    yield f"data: {json.dumps({...})}\n\n"
    ...
```

### 4.3 Action 意图细分

当 pipeline 处于 paused 状态时，用户的新消息识别为 action 子类型：

| 用户消息 | 检测结果 | 动作 |
|---------|---------|------|
| "确认"/"继续"/"下一步" | `action:confirm` | 推进到下一 stage |
| "企业解析没问题" | `action:confirm` | 推进 |
| "策划案第三章改一下" | `action:modify` | 停在当前 stage，重新生成 |
| "色调再冷一点" | `action:modify` | 停在当前 stage，重新生成 |
| "重新开始" | `action:restart` | 重置整个 pipeline |

---

## 5. Pipeline Session 状态

存储在 conversation 的 `metadata_json` 中（与 `VisualConceptContext` 模式一致）：

```json
{
  "pipeline": {
    "status": "paused",
    "current_stage": "company_analysis",
    "completed_stages": [],
    "sop_workflow_id": null,
    "project_context": {
      "company_name": "华为",
      "industry": "科技",
      "requirement_summary": "设计一套3D展示幕墙方案",
      "company_profile": null,
      "proposal_output": null,
      "visual_output": null
    },
    "stage_outputs": {
      "company_analysis": { "output_id": "uuid", "summary": "..." },
      "proposal_generation": null,
      "visual_prompt": null,
      "export": null
    },
    "started_at": "2026-06-09T12:00:00Z"
  }
}
```

状态转换：

```
[无 pipeline] → running(company_analysis)
running(company_analysis) → paused(company_analysis)    // 执行完，等确认
paused(company_analysis) + action:confirm → running(proposal_generation)
paused(company_analysis) + action:modify → running(company_analysis)  // 重跑
running(proposal_generation) → paused(proposal_generation)
...
running(export) → completed
```

---

## 6. 暂停恢复机制

### 6.1 暂停

每个暂停阶段执行完 Skill 后：

1. 保存 Skill 输出到 `stage_outputs`
2. 设置 `pipeline.status = "paused"`
3. 通过 SSE 推送结果卡片 + `action_buttons` block
4. 保存 assistant message（含 pipeline state 到 metadata）

### 6.2 恢复

用户发新消息时：

1. `_load_pipeline_state(conv)` 从最近 assistant message 的 metadata 中恢复
2. 如果 `status == "paused"`，走 `_handle_sop_pipeline_resume()`
3. 根据 action 类型分派：
   - `confirm` → 推进到下一 stage
   - `modify` → 用用户消息作为额外上下文重跑当前 stage
   - `restart` → 重置 pipeline state

### 6.3 卡片按钮

每个暂停阶段的 action_buttons：

```
Stage 1 (企业画像):
  [✓ 确认企业画像，继续]  [↻ 重新生成]

Stage 2 (策划案):
  [✓ 确认策划案，继续]  [✎ 我有修改意见]

Stage 3 (视觉方案):
  [使用方案 A]  [使用方案 B]  [两个都用]
```

---

## 7. 前端改动

### 7.1 Welcome Screen

在现有 5 张技能卡片中新增第 6 张：

```tsx
{
  icon: Rocket,
  title: "完整方案",
  description: "从企业解析到导出的端到端方案生成",
  message: "帮我设计一套完整的3D幕墙方案",
}
```

### 7.2 Pipeline 进度指示

在消息列表顶部（或侧边栏对话标题下方）可选展示 pipeline 进度条：

```
企业解析 ✓ → 策划案 ✓ → 视觉方案 ◉ → 导出 ○
```

MVP 阶段可用简化版本（在文本消息中展示进度），后续再做独立 UI 组件。

### 7.3 Action Buttons

现有的 `ActionButtonsBlock` 已支持点击后锁定、回调 `onAction`，无需改动。

---

## 8. 后端改动清单

| 文件 | 改动内容 | 估时 |
|------|---------|------|
| `services/intent_service.py` | 新增 `sop_pipeline` 关键词 + action 细分 | 小 |
| `services/conversation_service.py` | `_handle_sop_pipeline()` + `_handle_sop_pipeline_resume()` + `_load/save_pipeline_state()` | 大 |
| `services/conversation_service.py` | `process_message_stream()` 新增路由 + paused 检测 | 小 |
| `skills/builtins/proposal_generation.py` | 支持 `company_profile` dict 作为输入 | 小 |
| `skills/builtins/export.py` | pipeline 模式下简化审核门 | 小 |
| `components/chat/welcome-screen.tsx` | 新增第 6 张卡片 | 小 |

**不改动**：Skill 基类、数据库模型、SOP 数据模型、现有 6 个 Skill 的核心逻辑、BlockRenderer。

---

## 9. 上下文传递（Stage 间数据流）

```
用户消息
  │
  ├─→ Stage 1: company_analysis
  │     输入: user_message
  │     输出: company_profile dict
  │
  ├─→ Stage 2: proposal_generation
  │     输入: company_profile (from Stage 1) + user_message + RAG
  │     输出: proposal markdown + sections_meta
  │
  ├─→ Stage 3: visual_prompt + image_generation
  │     输入: proposal output (from Stage 2) + visual_direction (from company_profile)
  │     输出: visual_strategy + positive/negative prompts + 2 images
  │
  └─→ Stage 4: export
        输入: proposal content + images metadata (from Stage 2+3)
        输出: file_path (Word/PPT)
```

每个 stage 的输出存入 `pipeline.stage_outputs[stage_name]`，作为下一 stage 的输入。

---

## 10. 错误处理

| 场景 | 处理方式 |
|------|---------|
| Skill 执行失败 | 展示错误信息 + 保留 paused 状态，用户可重试 |
| 用户长时间不回复 | Pipeline state 持久化在 conversation metadata，随时可恢复 |
| 用户中途离开对话 | 返回同一对话时，从 metadata 恢复 pipeline，提示"你有未完成的方案流程" |
| LLM 超时 | 跟现有 skill 执行超时处理一致，回退到 conversational |

---

## 11. MVP 验收标准

1. ✅ 用户输入"给XX公司设计一套3D幕墙方案"，系统能自动启动 pipeline
2. ✅ 缺少企业名称时，立即要求补充（不走 LLM）
3. ✅ 企业解析完成后暂停，展示卡片 + 确认按钮
4. ✅ 用户确认后自动进入策划案生成
5. ✅ 策划案完成后暂停，用户可确认或微调
6. ✅ 视觉方案生成 2 张效果图，用户可选择
7. ✅ 确认后自动导出 Word 文档
8. ✅ 全程在同一个对话窗口完成
9. ✅ 用户随时可以微调任意阶段

---

## 12. 后续扩展方向（不在 MVP 范围）

- 抽象为通用 PipelineRunner 引擎
- SOP 可配置确认节点（管理员控制哪些 stage 需暂停）
- 多条管线支持（如"活动发布方案管线"、"展厅项目管线"）
- quality_check Skill 接入
- 章节级 HITL 审核 UI
- Pipeline 进度条独立 UI 组件
