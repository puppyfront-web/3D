# Agent 工作流规格说明 (AGENT_SPEC)

> 本文档定义 3D 展示幕墙 AI 专家系统的 Agent 工作流架构和实现规则。

---

## 1. 设计原则

### 1.1 核心原则

- **SOP 驱动**：Agent 执行流程由配置的 SOP 定义，不是硬编码
- **RAG 增强**：所有生成都基于检索到的真实资料，不编造
- **可追溯**：每次生成记录所有引用来源和使用的模板/规则
- **可审核**：所有 AI 输出必须经过人工审核才能最终导出
- **可配置**：Prompt 模板、SOP 步骤、质量标准都通过后台管理

### 1.2 不做的事

- ❌ 不让 Agent 自由发挥，不受 SOP 约束
- ❌ 不允许编造案例、报价、参数
- ❌ 不跳过人工审核直接输出
- ❌ 不在代码中硬编码 Prompt

---

## 2. Agent 架构

### 2.1 整体架构

```text
┌─────────────────────────────────────────┐
│              Agent 调度层                 │
│  (接收任务 → 选择 Agent → 分发执行)       │
├─────────────────────────────────────────┤
│                                         │
│  ┌───────────┐  ┌───────────┐          │
│  │ 企业解析   │  │ 策划案专家  │          │
│  │ Agent     │  │ Agent     │          │
│  └───────────┘  └───────────┘          │
│                                         │
│  ┌───────────┐  ┌───────────┐          │
│  │ 视觉创意   │  │ 质量检查   │          │
│  │ Agent     │  │ Agent     │          │
│  └───────────┘  └───────────┘          │
│                                         │
├─────────────────────────────────────────┤
│              公共服务层                   │
│  LLMService | RetrievalService          │
│  ExportService | FeedbackService        │
└─────────────────────────────────────────┘
```

### 2.2 Agent 接口

每个 Agent 必须实现统一接口：

```python
class BaseAgent(ABC):
    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        """执行 Agent 任务"""
        pass

    @abstractmethod
    async def validate_input(self, context: AgentContext) -> ValidationResult:
        """验证输入是否完整"""
        pass

    @abstractmethod
    async def quality_check(self, result: AgentResult) -> QualityReport:
        """质量自检"""
        pass

class AgentContext:
    project_id: str
    company_profile: dict | None
    project_requirement: dict | None
    sop_steps: list[dict] | None
    rag_context: ContextPack | None
    user_instructions: str | None

class AgentResult:
    output_type: str
    content: dict
    used_cases: list[str]
    used_documents: list[str]
    used_chunks: list[str]
    used_external_sources: list[dict]
    external_search_summary: dict | None
    used_sop_version: str | None
    used_prompt_templates: list[str]
    missing_info: list[str]
    quality_score: float | None
    status: str  # draft | completed | needs_review
```

### 2.3 联网搜索 Tool 边界

`web_search` 采用**双触发模式**：在企业解析阶段强制触发收集客观信息，在后续阶段作为内部 RAG 的补充。

#### 触发模式

- **模式 A — 强制触发**：`company_analysis` 阶段，用户输入企业信息（公司名 / 品牌 / 行业）后**必定执行**。自动收集客观信息（主营业务、产品线、行业定位、公开动态），填充画像客观字段，仅主观字段交用户确认。
- **模式 B — 补充触发**：`proposal_generation` 等后续阶段，内部 `knowledge_search` / `case_search` 命中不足时执行。

触发判定由服务端代码显式控制，**不让 LLM 自主决定是否调用**。

允许触发的前提：

- 企业信息输入后强制触发（模式 A）
- 或内部 `knowledge_search` 和 `case_search` 结果不足以回答问题（模式 B）
- 搜索目标可以限定到公开网页、白名单域名或可信搜索提供方

禁止触发的场景：

- 报价、工期、施工承诺等应由人工确认的内容
- 需要登录、付费、私有链接或客户私密资料的页面
- 主观偏好（品牌调性、视觉风格）— 此类信息不外搜，由用户确认

#### 降级策略

web_search 失败（超时 / 无结果 / 低置信度 / provider 不可用）时**不阻断流程**：

1. 客观字段标记 `verified: false`
2. 在 `missing_info` 追加「未核实」项
3. 继续基于「用户输入 + 内部 RAG」生成企业画像

#### 客观 / 主观字段拆分

- **客观字段**（web_search 自动填充，标注来源 + 置信度）：`industry`、`business_type`、`core_products`、`market_position`、`public_news`、`brand_official_info`
- **主观字段**（必须用户确认，不自动填充）：`brand_keywords`、`target_audience`、`communication_goal`、`visual_preferences`、`forbidden_expressions`

详细字段结构与触发流程见 `docs/superpowers/specs/2026-06-25-web-search-tool-boundary.md`。

#### 输出结构

`web_search` 的输出必须先归一化再进入生成链路：

```json
{
  "query": "xxx",
  "status": "ok | degraded | failed",
  "results": [
    {
      "title": "来源标题",
      "url": "https://...",
      "domain": "example.com",
      "snippet": "命中的摘要",
      "published_at": "2026-06-20",
      "source_type": "news | official | article",
      "confidence": 0.82
    }
  ],
  "summary": {
    "key_points": ["..."],
    "conflicts": ["..."],
    "missing_info": ["..."],
    "recommended_usage": "可引用 / 仅背景参考 / 需人工确认"
  },
  "degraded_reason": "timeout | no_results | low_confidence | provider_unavailable"
}
```

外部搜索结果不能直接拼接给 LLM。必须先做一层结构化总结，提取关键信息、冲突信息和待确认项，再写入 `rag_context` 或 Artifact。

---

## 3. 企业解析 Agent

### 3.1 执行流程

```text
开始
  │
  ▼
读取项目信息（企业名、行业、需求描述）
  │
  ▼
读取上传资料（文档、图片）
  │
  ▼
RAG 检索同行业企业画像
  │
  ▼
强制调用 web_search 收集企业客观信息（模式 A）
  │  └─ 失败/降级 → 客观字段标记「未核实」，进入 missing_info，不阻断
  ▼
web_search 结果归一化（key_points / conflicts / missing_info / sources）
  │
  ▼
自动填充客观字段（标注来源 + 置信度）
  │
  ▼
读取企业解析 SOP
  │
  ▼
加载企业解析 Prompt 模板
  │
  ▼
组装 Context Pack（含 web_search 总结）
  │
  ▼
调用 LLM 生成企业画像（客观字段引用搜索结果，主观字段留待确认）
  │
  ▼
质量自检
  │
  ▼
识别缺失信息（主观字段 + 未核实的客观字段）
  │
  ▼
保存 company_profile
  │
  ▼
记录 generation_output + 引用（含 used_external_sources）
  │
  ▼
记录 retrieval_log
  │
  ▼
返回结果（客观字段已填充，仅主观/未核实项交用户确认）
```

### 3.2 输入要求

```text
必须：
  - 企业名称
  - 行业（或可推断）

可选：
  - 企业简介
  - 上传资料
  - 项目需求
  - 用户补充说明
```

> 注：客观字段（行业、业务类型、主营产品等）由 web_search 自动收集填充；主观字段（品牌调性、视觉偏好、传播目标等）由用户在确认环节提供或修改。详见 §2.3 与 `docs/superpowers/specs/2026-06-25-web-search-tool-boundary.md`。

### 3.3 输出结构

客观字段由 web_search 自动填充，结构为 `{value, verified, source, confidence}`；主观字段由用户确认，结构保持原样。

```json
{
  "company_profile": {
    "industry": {
      "value": "汽车",
      "verified": true,
      "source": {
        "title": "...",
        "url": "https://...",
        "domain": "example.com",
        "published_at": "2026-06-20"
      },
      "confidence": 0.85
    },
    "business_type": {
      "value": "汽车制造与销售",
      "verified": true,
      "source": { "url": "https://...", "domain": "example.com" },
      "confidence": 0.82
    },
    "core_products": {
      "value": ["SUV", "新能源汽车"],
      "verified": true,
      "source": { "url": "https://...", "domain": "example.com" },
      "confidence": 0.78
    },
    "market_position": {
      "value": null,
      "verified": false,
      "source": null,
      "confidence": 0
    },
    "brand_keywords": ["科技", "运动", "年轻"],
    "target_audience": "25-40岁都市白领",
    "communication_goal": "品牌形象升级，展示科技实力",
    "visual_preferences": ["科技感", "动感", "简约"],
    "forbidden_expressions": ["竞品对比", "降价促销"],
    "missing_info": [
      "⚠️ market_position 未能从公开来源核实，需要进一步确认",
      "主推车型需要进一步确认",
      "品牌VI规范需要进一步确认"
    ]
  },
  "analysis": {
    "brand_position": "...",
    "scene_analysis": "...",
    "recommended_visual_direction": "...",
    "recommended_creative_themes": []
  }
}
```

### 3.4 质量检查项

```text
✅ 行业是否已识别
✅ 品牌关键词是否已提取
✅ 目标受众是否已分析
✅ 是否标记了缺失信息
✅ 客观字段是否标注了来源与核实状态（verified / source / confidence）
✅ 未核实的客观字段是否进入了 missing_info
✅ 是否引用了真实资料（如有上传）
❌ 是否编造了不存在的品牌信息
```

---

## 4. 策划案专家 Agent

### 4.1 执行流程

```text
开始
  │
  ▼
验证前置条件（企业画像是否已确认）
  │
  ▼
读取项目需求
  │
  ▼
读取企业画像
  │
  ▼
读取策划案 SOP
  │
  ▼
RAG 检索案例（按行业、场景、风格匹配）
  │
  ▼
RAG 检索文档（按需求关键词检索）
  │
  ▼
必要时调用 web_search（仅补充外部公开信息）
  │
  ▼
汇总外部搜索结果（关键信息 / 冲突 / 待确认项）
  │
  ▼
检索技术规则（按屏幕类型、场景）
  │
  ▼
加载策划案 Prompt 模板
  │
  ▼
加载策划案内容模板
  │
  ▼
组装 Context Pack
  │
  ▼
生成策划案大纲
  │
  ▼
生成完整策划案（逐章节）
  │
  ▼
执行质量检查
  │
  ▼
标记待确认项
  │
  ▼
保存 generation_output + 引用
  │
  ▼
记录 retrieval_log
  │
  ▼
返回结果
```

### 4.2 前置条件

```text
必须已完成：
  - 企业画像已确认（company_profile.status = 'confirmed'）
  - 至少有项目基本需求描述
```

### 4.3 输出结构

策划案内容结构：

```text
# [项目名称] 3D 展示方案策划案

## 一、需求理解
  对客户需求的理解和复述

## 二、企业解析摘要
  基于企业画像的关键信息摘要

## 三、项目背景
  项目背景和上下文

## 四、项目目标
  明确的项目目标

## 五、创意主题
  推荐的创意方向和主题
  （含多个方案供选择）

## 六、方案亮点
  方案的核心竞争力

## 七、视觉方向
  推荐的视觉风格和方向
  配色建议
  构图建议

## 八、参考案例
  引用的实际案例列表
  [案例名] — [相似度] — [引用来源]
  （每个案例必须是真实案例）

## 九、实施建议
  时间线建议
  资源需求
  注意事项

## 十、风险与待确认事项
  ⚠️ 屏幕尺寸需要进一步确认
  ⚠️ 预算范围需要进一步确认
  ⚠️ 施工条件需要现场勘测

---
📎 引用来源
  - 案例：[案例A]、[案例B]
  - 文档：[文档A] 第3-5页
  - SOP：策划案生成流程 v1.2
  - 模板：科技风策划案模板
```

### 4.4 禁止行为

```text
❌ 编造案例（所有案例必须来自案例库）
❌ 编造报价（报价必须标记为"需要进一步确认"）
❌ 编造屏幕参数（参数必须来自需求录入或标记缺失）
❌ 编造工期（工期必须标记为"需要进一步确认"）
❌ 承诺最终投屏效果（只能描述预期方向）
```

### 4.5 质量检查项

```text
✅ 所有章节是否完整
✅ 是否引用了真实案例
✅ 是否标记了缺失信息
✅ 报价是否标记为待确认
✅ 工期是否标记为待确认
✅ 案例引用是否可追溯
✅ 是否遵循 SOP 步骤
❌ 是否包含编造内容
❌ 是否遗漏关键章节
```

---

## 5. 视觉创意 Agent

### 5.1 执行流程

```text
开始
  │
  ▼
读取项目需求
  │
  ▼
读取企业画像
  │
  ▼
读取视觉风格库
  │
  ▼
RAG 检索相似视觉案例
  │
  ▼
选择 Prompt 模板（按风格和场景匹配）
  │
  ▼
组装 Context Pack
  │
  ▼
生成视觉策略
  │
  ▼
生成正向 Prompt
  │
  ▼
生成负向 Prompt
  │
  ▼
调用图片生成接口
  │
  ▼
保存图片和 Prompt
  │
  ▼
记录 generation_output + 引用
  │
  ▼
返回结果
```

### 5.2 输入要求

```text
必须：
  - 企业画像
  - 视觉风格选择（或 AI 推荐）

可选：
  - 参考图
  - 场地图
  - 屏幕参数
```

### 5.3 输出结构

```json
{
  "visual_strategy": {
    "concept": "...",
    "key_elements": [],
    "color_palette": [],
    "composition": "...",
    "mood": "..."
  },
  "positive_prompt": "a stunning 3D display wall, ...",
  "negative_prompt": "ugly, blurry, low quality, ...",
  "composition_advice": "...",
  "reference_cases": [
    {
      "case_id": "uuid",
      "title": "...",
      "image_url": "..."
    }
  ],
  "notes": "...",
  "generated_images": [
    {
      "image_url": "...",
      "prompt_used": "...",
      "model": "...",
      "seed": 12345
    }
  ]
}
```

### 5.4 质量检查项

```text
✅ Prompt 是否符合屏幕参数约束
✅ 风格是否与客户偏好匹配
✅ 是否参考了真实视觉案例
✅ 负向 Prompt 是否完整
❌ 是否包含侵权元素
❌ 是否与客户禁忌冲突
```

---

## 6. 图片生成 Provider 抽象

### 6.1 接口定义

```python
class ImageGenerationService(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        negative_prompt: str | None = None,
        width: int = 1024,
        height: int = 1024,
        reference_image: str | None = None,
        **kwargs
    ) -> ImageGenerationResult:
        pass

class ImageGenerationResult:
    image_urls: list[str]
    model: str
    parameters: dict
    latency_ms: int
```

### 6.2 Provider 实现

```text
MVP 阶段：
  - MockProvider：返回占位图，用于开发测试
  - OpenAIProvider：接入 DALL-E API

后续扩展：
  - StableDiffusionProvider
  - MidjourneyProvider
  - ComfyUIProvider
  - 自定义模型 Provider
```

---

## 7. LLM 调用规范

### 7.1 Service 抽象

```python
class LLMService(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> LLMResult:
        pass

    @abstractmethod
    async def chat_with_context(
        self,
        system_prompt: str,
        context: ContextPack,
        user_message: str,
        **kwargs
    ) -> LLMResult:
        pass
```

### 7.2 Prompt 模板化

所有 Prompt 必须使用模板，禁止硬编码：

```python
# ❌ 错误：硬编码 Prompt
prompt = f"你是一个3D展示幕墙专家，请分析以下企业：{company_name}"

# ✅ 正确：使用模板
template = await prompt_template_service.get_template(
    task_type="company_analysis",
    scene="default"
)
prompt = template.render(variables={
    "company_name": company_name,
    "industry": industry,
    ...
})
```

### 7.3 幻觉防护

```text
系统 Prompt 必须包含以下约束：
  - 只使用提供的案例和资料
  - 不编造案例或数据
  - 缺失信息必须标记为"需要进一步确认"
  - 报价和工期不能给出具体数字
  - 明确标注引用来源
```

---

## 8. 工作流编排

### 8.1 项目全流程

```text
创建项目
    │
    ▼
录入信息（企业 + 需求 + 场地 + 视觉偏好）
    │
    ▼
上传资料
    │
    ▼
┌──────────────┐
│ 企业解析 Agent │ → 生成企业画像 → 人工确认
└──────┬───────┘
       │
       ▼
┌────────────────┐
│ 策划案专家 Agent  │ → 生成策划案 → 人工编辑
└──────┬─────────┘
       │
       ▼
┌────────────────┐
│ 视觉创意 Agent    │ → 生成视觉方案 → 人工确认
└──────┬─────────┘
       │
       ▼
审核检查 → 导出
       │
       ▼
反馈沉淀 → 更新案例库/模板
```

### 8.2 中断与恢复

```text
每个 Agent 执行结果保存为 generation_output
支持版本管理
支持从任意步骤重新执行
人工编辑后保存新版本
```

---

## 9. 后续扩展

MVP 后可扩展的 Agent 能力：

- **报价估算 Agent**：基于历史案例和参数估算
- **施工方案 Agent**：生成施工建议
- **效果评估 Agent**：自动评估生成质量
- **多方案对比 Agent**：生成多个方案供选择
- **客户反馈分析 Agent**：分析客户反馈优化模板
