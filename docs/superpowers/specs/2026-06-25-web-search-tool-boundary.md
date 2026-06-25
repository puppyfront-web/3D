# Web Search Tool 最小落地方案

> 修订: 2026-06-25（v2）— 触发策略从「仅补充内部不足」改为「双触发模式」
> 原因: 客户反馈，企业解析阶段应主动联网收集客观信息，减少用户手工填写负担，主观信息才交给用户确认。

## 背景

当前系统只有内部检索能力：

- Tool Registry 仅注册 `case_search`、`knowledge_search`、`sop_load`、`template_load`、`prompt_template_load`、规则查询等内部工具
- Agent/Conversation 路由只会调固定 Skill，不会在执行期按需调用外部检索
- Artifact 与 SkillResult 目前只追踪 `used_cases / used_documents / used_chunks`

这意味着 MVP 能回答内部知识库问题，但不能可靠处理外部公开信息、近期行业动态、品牌官网资料核验等场景。

## 目标

新增一个受控的 `web_search` Tool，满足以下要求：

- **企业信息输入后强制联网**：自动收集客观公开信息，填充企业画像的客观字段
- **内部知识不足时补充联网**：作为内部 RAG 的兜底检索路径
- 不允许无边界自由上网
- 搜索结果必须可追溯
- 搜索结果必须先总结，再进入生成链路
- 最终 Artifact 必须记录外部来源与总结
- **搜索失败不阻断流程**：降级标记「未核实」，继续生成

---

## 触发策略（核心）

`web_search` 有两种触发模式，服务端代码显式控制，**不让 LLM 自主决定是否调用**。

### 模式 A：强制触发（mandatory）

**触发点**：`company_analysis` 阶段，用户输入企业信息（公司名 / 品牌 / 行业）后，**必定执行**。

**目的**：自动收集企业客观信息，减少用户手工填写，客观字段由系统填充并标注来源。

**检索目标**：
- 企业主营业务、产品线
- 行业定位、市场地位（公开可核实部分）
- 近期公开动态、报道
- 品牌官网公开信息

**不允许通过搜索填充**（主观 / 商业承诺 / 无法核实）：
- 品牌调性偏好、视觉风格倾向
- 沟通目标、传播诉求
- 预算、报价、工期承诺
- 客户私有信息

### 模式 B：补充触发（fallback）

**触发点**：`proposal_generation` 等后续阶段，内部 `knowledge_search` / `case_search` 命中不足时。

**判断条件**：
- 内部检索结果与当前问题的相关性低于阈值
- 问题明确依赖近期信息或外部公开资料（行业趋势、竞品公开案例）

### 触发判定流程

```
用户输入企业信息
    │
    ▼
[模式 A 强制] 调用 web_search 收集客观信息
    │
    ▼
来源校验 + 冲突归纳 + 结构化总结
    │
    ├─ 成功 → 自动填充客观字段（标注来源）
    │
    └─ 失败/降级 → 客观字段标记「未核实」，进入 missing_info
    │
    ▼
组装 company_analysis_card
    │
    ▼
仅将主观字段 + 未核实项交给用户确认
```

---

## 客观 / 主观字段拆分

企业画像字段按「能否从公开来源客观核实」拆分，决定填充方式与确认方式。

### 客观字段（web_search 自动填充，标注来源 + 置信度）

| 字段 | 说明 |
|------|------|
| `industry` | 行业分类 |
| `business_type` | 业务类型 |
| `core_products` | 主营产品 / 服务线 |
| `market_position` | 市场地位（仅公开可核实部分） |
| `public_news` | 近期公开动态 / 报道 |
| `brand_official_info` | 品牌官网公开信息 |

填充后字段结构：
```json
{
  "industry": {
    "value": "新能源汽车",
    "verified": true,
    "source": {
      "title": "...",
      "url": "https://...",
      "domain": "...",
      "published_at": "2026-06-20"
    },
    "confidence": 0.85
  }
}
```

### 主观字段（必须用户确认，不自动填充）

| 字段 | 说明 |
|------|------|
| `brand_keywords` | 品牌调性关键词 |
| `target_audience` | 目标受众（无公开数据时） |
| `communication_goal` | 传播 / 沟通目标 |
| `visual_preferences` | 视觉风格偏好 |
| `forbidden_expressions` | 表达禁忌 |

这些字段由用户在确认卡片中填写或修改，系统不预设。

---

## 降级策略

**决策**：web_search 失败时**不阻断流程**，继续生成企业画像并降级标记。

### 触发降级的条件

满足任一即降级：
- 请求超时 / 网络错误
- 返回 0 条结果
- 所有结果置信度低于阈值（默认 0.5）
- 命中结果全部被黑名单过滤
- 搜索 provider 不可用

### 降级处理

1. 客观字段标记 `verified: false, source: null`
2. 在 `missing_info` 中追加：
   ```
   ⚠️ 需要进一步确认：[字段名] 未能从公开来源核实
   ```
3. 在 `external_search_summary` 中记录降级原因：
   ```json
   {
     "status": "degraded",
     "reason": "timeout | no_results | low_confidence | provider_unavailable",
     "attempted_queries": ["..."]
   }
   ```
4. 继续基于「用户输入 + 内部 RAG」生成企业画像，主观字段照常交用户确认

**禁止**：因搜索失败而抛错中断整个 `company_analysis` 阶段。

---

## 执行边界

### 允许调用

- `company_analysis` 阶段强制调用（模式 A）
- 内部 `knowledge_search` 无法覆盖的问题（模式 B）
- 依赖外部公开资料、近期信息、行业动态的问题
- 需要核验品牌官网、政府公开文件、行业协会公开资料的问题

### 禁止调用

- 报价、工期、施工安全承诺等高风险承诺问题
- 登录后内容、付费内容、客户私有链接
- 宽泛的「帮我去网上看看」且无业务边界的问题
- 仅凭内部案例库和知识库即可回答的问题（模式 B 不触发）

### 域名边界

优先级建议：

1. 官方站点：品牌官网、政府站、行业协会、展会主办方
2. 白名单媒体：经业务确认的行业媒体
3. 通用搜索结果：仅作补充背景，不能单独作为高置信结论依据

至少需要在配置层支持：

- 允许域名白名单
- 禁止域名黑名单
- 单次最大结果数
- 单次抓取最大页面数
- 超时与重试上限
- 置信度阈值（低于则降级）

---

## 返回结构

`web_search.execute()` 返回结构：

```json
{
  "query": "深圳 裸眼3D 商业综合体 案例",
  "status": "ok | degraded | failed",
  "results": [
    {
      "title": "示例标题",
      "url": "https://example.com/article",
      "domain": "example.com",
      "snippet": "摘要片段",
      "published_at": "2026-06-20",
      "source_type": "official",
      "confidence": 0.86
    }
  ],
  "summary": {
    "key_points": ["..."],
    "conflicts": ["..."],
    "missing_info": ["..."],
    "recommended_usage": "可引用 | 仅背景参考 | 需人工确认"
  },
  "degraded_reason": null
}
```

- `status`：`ok` = 正常返回可信结果；`degraded` = 有结果但置信度低 / 部分失败；`failed` = 完全失败
- `degraded_reason`：降级时填写原因，供上游记录

---

## 搜索后的总结缺口

当前代码已有阶段性 summary，但还缺三层：

1. `web_search` 自身的结果总结（已定义在返回结构的 `summary`）
2. `company_analysis` 阶段对「客观字段填充情况」的总结
3. 最终 Artifact 对外部来源的引用摘要

已存在但不够的地方：

- `apps/api/app/services/plan_executor.py` 的 `_summarize_output()` 只汇总 `missing_count / sections_count / images_count`
- `apps/api/app/services/conversation_service.py` 的 `stage_summary` 只展示阶段耗时和基础数量指标
- `GenerationOutput`、`GenerationOutputCreate`、`SkillResult` 还没有 `used_external_sources` 和 `external_search_summary`

因此最小落地必须补：

- Tool 级 summary：对搜索结果做结构化归纳（已在返回结构中）
- Stage 级 summary：展示「命中外部来源数 / 冲突数 / 待确认项数 / 降级状态」
- Artifact 级 summary：把外部来源摘要沉淀到最终产物

---

## 最小代码改造点

### 1. Tool 层

- 新增 `apps/api/app/tools/builtins/web_search.py`
- 在 `apps/api/app/tools/registry.py` 中注册 `WebSearchTool`
- 在 `ToolContext` 中补充配置依赖（白名单 / 黑名单 / 阈值 / 超时），不要把整个浏览器能力塞进 Tool
- Tool 内部实现降级逻辑：失败时返回 `status: degraded/failed` 而非抛错

### 2. Skill / Agent 结果结构

建议补充字段：

- `SkillResult.used_external_sources: list[dict]`
- `SkillResult.external_search_summary: dict | None`
- `GenerationOutput.used_external_sources`
- `GenerationOutput.external_search_summary`
- 对应 schema 同步更新

### 3. 编排层

调用策略：

- **`company_analysis` 阶段**：模式 A，先调 `web_search` 收集客观信息 → 归纳总结 → 自动填充客观字段（标注来源）→ 仅主观字段交用户确认
- **后续阶段**（`proposal_generation` 等）：模式 B，先跑 `knowledge_search` → 判断是否不足 → 不足时才调 `web_search` → 把 `web_search.summary` 写回上下文

不要让 LLM 自主决定抓多少页、访问哪些站点。搜索边界必须由服务端代码控制。

### 4. 企业画像字段结构

`company_analysis_card` 改造：

- 客观字段从「裸值」改为 `{value, verified, source, confidence}` 结构
- 主观字段保持原结构，但 UI 上标注「需用户确认」
- 缺失的客观字段（含降级未核实的）汇总进 `missing_info`

### 5. 会话 / 展示层

补充以下展示：

- `stage_summary.metrics.external_source_count`
- `stage_summary.metrics.external_conflict_count`
- `stage_summary.metrics.degraded`（是否发生降级）
- `artifact` 中的 `used_external_sources`
- `artifact` 中的 `external_search_summary`

---

## 推荐实施顺序

1. 定义 `web_search` Tool 接口与返回结构（含降级状态）
2. 补充 `SkillResult / GenerationOutput / schemas` 的外部来源字段
3. 接入一个受控搜索 provider（MVP 可先接一个，预留 provider 抽象）
4. 改造 `company_analysis` 阶段：强制搜索 + 客观字段自动填充 + 主观字段待确认 + 降级处理
5. 在后续阶段（`proposal_generation`）增加「内部不足时再外搜」的逻辑（模式 B）
6. 补齐 SSE summary 和 Artifact 展示
7. 增加测试：强制触发、补充触发、降级场景、追溯、禁用场景

---

## 验收标准

- 用户输入企业信息后，`company_analysis` 必定触发 `web_search`（模式 A）
- 客观字段由搜索结果自动填充并标注来源
- 主观字段交给用户确认，系统不预设
- web_search 超时 / 无可信结果时，流程不中断，客观字段标记「未核实」并进入 `missing_info`
- 后续阶段内部知识不足时，可触发 `web_search`（模式 B）
- 内部命中充足时，后续阶段不会默认外搜
- 结果包含可追溯 URL 和域名
- 最终产物能看到外部来源摘要
- 对外部来源冲突和缺失项有明确标注
- 不会访问登录页、私有页和黑名单域名
