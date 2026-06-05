# RAG 检索规格说明 (RAG_SPEC)

> 本文档定义 3D 展示幕墙 AI 专家系统的 RAG 检索架构和实现规则。

---

## 1. 设计原则

### 1.1 核心原则

- **分层管理**：知识资产按类型分层存储和检索，不做大杂烩
- **可追溯**：所有检索结果必须记录来源，生成输出必须记录引用
- **结构化**：检索结果经过 Context Pack 组装后传给 Agent，不是原始 chunk
- **可配置**：检索策略、权重、过滤规则可通过管理后台调整

### 1.2 不做的事

- ❌ 不把所有文档放在一个向量库里无差别检索
- ❌ 不把检索结果原样塞给模型
- ❌ 不允许生成无法追溯来源的内容
- ❌ 不在代码中硬编码检索策略

---

## 2. 知识资产分层

### 2.1 分层架构

```text
┌─────────────────────────────────────┐
│          知识资产分层体系              │
├─────────────────────────────────────┤
│                                     │
│  Layer 1: 结构化知识                  │
│  ├─ 案例库 (cases)                   │
│  ├─ 企业画像库 (company_profiles)     │
│  └─ 技术规则库 (technical_rules)      │
│                                     │
│  Layer 2: 半结构化知识                │
│  ├─ SOP 工作流 (sop_workflows)       │
│  ├─ Prompt 模板 (prompt_templates)   │
│  ├─ 策划案模板 (proposal_templates)  │
│  ├─ 视觉风格库 (visual_styles)       │
│  └─ 质量标准 (quality_rules)          │
│                                     │
│  Layer 3: 非结构化知识                │
│  ├─ 文档 chunks (document_chunks)    │
│  ├─ 图片案例 (images + tags)         │
│  └─ 上传资料 (documents)             │
│                                     │
└─────────────────────────────────────┘
```

### 2.2 检索优先级

```text
1. 结构化知识（案例库、技术规则）— 优先匹配，精确度高
2. 半结构化知识（SOP、模板、风格）— 按场景匹配
3. 非结构化知识（文档 chunks）— 向量检索补充
```

---

## 3. 检索流程

### 3.1 完整链路

```text
用户需求输入
    │
    ▼
┌──────────────┐
│  任务识别     │  判断：企业解析 / 策划案 / 视觉生成 / 其他
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  需求结构化   │  提取：行业、场景、目标、风格、屏幕类型等
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  检索意图改写  │  生成多个检索 query
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  元数据过滤   │  按 industry, scene, screen_type, quality_score 过滤
└──────┬───────┘
       │
       ▼
┌──────────────────────────────┐
│  并行检索                      │
│  ├─ 关键词检索（全文搜索）       │
│  ├─ 向量检索（语义相似度）       │
│  └─ 结构化查询（案例库/规则库）  │
└──────┬───────────────────────┘
       │
       ▼
┌──────────────┐
│  简单 Rerank  │  综合评分：相似度 + 质量分 + 复用权重
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Context Pack  │  组装结构化上下文
│   组装        │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Agent 生成   │  使用 Context Pack 生成结果
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  检索日志     │  记录完整检索过程
└──────────────┘
```

---

## 4. 文档处理

### 4.1 支持的文档类型

| 格式 | 解析方式 | 备注 |
|------|----------|------|
| PDF | PyMuPDF / pdfplumber | 支持图文混排 |
| PPT/PPTX | python-pptx | 提取文字和备注 |
| DOC/DOCX | python-docx | 按段落提取 |
| 图片 | OCR / 标签模型 | 生成描述和标签 |
| TXT/MD | 直接读取 | — |

### 4.2 Chunk 切分策略

```text
切分规则：
  - 优先按章节标题切分
  - 单个 chunk 最大 500 字（可配置）
  - chunk 之间重叠 50 字（可配置）
  - 保留章节标题和页码信息

元数据记录：
  - document_id: 来源文档
  - section_title: 章节标题
  - page_number: 页码
  - chunk_type: text / table / image_description
  - metadata_json: 扩展信息
```

### 4.3 Embedding 策略

```text
模型：OpenAI-compatible Embedding API
维度：1536（可配置）
存储：pgvector
索引：IVFFlat 或 HNSW
```

---

## 5. 检索实现

### 5.1 关键词检索

```sql
-- 使用 PostgreSQL 全文搜索
SELECT *, ts_rank(to_tsvector('chinese', chunk_text), query) AS rank
FROM document_chunks, plainto_tsquery('chinese', :search_query) query
WHERE to_tsvector('chinese', chunk_text) @@ query
  AND (:industry_filter IS NULL OR metadata_json->>'industry' = :industry_filter)
ORDER BY rank DESC
LIMIT :limit;
```

### 5.2 向量检索

```sql
-- 使用 pgvector 余弦距离
SELECT *, 1 - (embedding <=> :query_embedding) AS similarity
FROM document_chunks
WHERE (:case_id_filter IS NULL OR case_id = :case_id_filter)
ORDER BY embedding <=> :query_embedding
LIMIT :limit;
```

### 5.3 混合检索评分

```python
# 综合评分公式
final_score = (
    0.4 * vector_similarity +      # 向量相似度
    0.2 * keyword_score +           # 关键词匹配
    0.2 * quality_score / 100 +    # 质量评分（案例）
    0.2 * reuse_weight             # 复用权重（案例）
)
```

---

## 6. Context Pack 结构

### 6.1 策划案 Context Pack

```json
{
  "company_profile": {
    "industry": "...",
    "brand_position": "...",
    "target_audience": "...",
    "visual_preferences": []
  },
  "project_requirement": {
    "type": "...",
    "goals": [],
    "screen_info": {},
    "site_info": {}
  },
  "matched_cases": [
    {
      "case_id": "uuid",
      "title": "...",
      "similarity": 0.85,
      "relevance": "..."
    }
  ],
  "referenced_documents": [
    {
      "document_id": "uuid",
      "title": "...",
      "chunks": [
        {
          "chunk_id": "uuid",
          "text": "...",
          "section": "...",
          "page": 5
        }
      ]
    }
  ],
  "sop_steps": [
    {
      "step": 1,
      "title": "...",
      "checklist": []
    }
  ],
  "technical_rules": [
    {
      "rule_id": "uuid",
      "title": "...",
      "content": "..."
    }
  ],
  "prompt_template": {
    "template_id": "uuid",
    "name": "..."
  },
  "missing_info": [
    "屏幕尺寸需要进一步确认",
    "预算范围需要进一步确认"
  ]
}
```

### 6.2 视觉 Context Pack

```json
{
  "company_profile": { ... },
  "project_requirement": { ... },
  "visual_style": {
    "style_id": "uuid",
    "name": "...",
    "parameters": {}
  },
  "similar_visual_cases": [
    {
      "case_id": "uuid",
      "images": [],
      "prompt_used": "..."
    }
  ],
  "prompt_template": {
    "template_id": "uuid",
    "positive_template": "...",
    "negative_template": "...",
    "variables": {}
  },
  "technical_constraints": {
    "resolution": "...",
    "aspect_ratio": "...",
    "color_mode": "..."
  },
  "missing_info": []
}
```

---

## 7. 检索日志

### 7.1 记录格式

每次检索必须记录：

```json
{
  "retrieval_log": {
    "id": "uuid",
    "user_query": "商业综合体裸眼3D方案",
    "structured_query": {
      "industry": "商业地产",
      "scene": "裸眼3D",
      "screen_type": null,
      "visual_style": null
    },
    "retrieved_items": {
      "cases": [{"id": "uuid", "score": 0.85}],
      "chunks": [{"id": "uuid", "score": 0.78}],
      "rules": [{"id": "uuid"}]
    },
    "selected_context": {
      "cases_count": 3,
      "chunks_count": 5,
      "rules_count": 2
    },
    "final_output_id": "uuid",
    "retrieval_method": "hybrid",
    "latency_ms": 250
  }
}
```

---

## 8. 质量保障

### 8.1 检索质量指标

```text
命中率：检索结果是否包含相关案例
相关性：检索结果与查询的语义相关度
覆盖率：是否能覆盖不同类型的知识来源
延迟：检索响应时间 < 2 秒
```

### 8.2 测试用例

| 输入 | 期望命中 |
|------|----------|
| 商业综合体裸眼3D需求 | 商业/综合体/裸眼3D 相关案例 |
| 汽车品牌发布需求 | 汽车/科技风/品牌发布 相关案例 |
| 户外LED大屏 | 户外/LED/广告 相关案例 |
| 低质量查询词 | 不应优先返回低质量案例 |

---

## 9. 后续扩展

MVP 后可扩展：

- Rerank 模型替换简单评分
- 多模态检索（图片向量）
- 知识图谱关联
- 用户反馈驱动的检索优化
- A/B 测试不同检索策略
