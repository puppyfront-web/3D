# RAG 检索改进路线图

> 本文档记录 RAG 系统的分阶段改进计划，明确 MVP 必做、建议做、后续做三层优先级。
>
> 创建日期：2026-06-10

---

## 1. 现状分析

### 1.1 当前实现摘要

| 维度 | 当前状态 |
|------|----------|
| Embedding | 默认 mock（SHA-256 伪随机），支持切换到 OpenAI 兼容 API |
| 向量存储 | pgvector `Vector(1536)`，优雅降级到 Text |
| 关键词检索 | ILIKE 模糊匹配（拆词最多 5 个） |
| 混合检索 | 三路并行（向量 + 关键词 + 案例结构化），去重合并取最高分 |
| Rerank | 无独立模型，仅去重合并（retriever 权重 0.4/0.2/0.2/0.2，router 权重 0.6/0.4 不一致） |
| Chunk | 默认 1000 字符 / 200 重叠（spec 要求 500/50） |
| 检索日志 | 仅记录 query / type / count / top_scores / latency_ms |
| 测试 | 5 个接口测试，无领域场景断言 |

### 1.2 已识别问题

1. **Embedding 默认 mock** — 检索结果无语义意义
2. **评分权重不统一** — retriever 和 router 各用一套
3. **Chunk 过大** — 1000/200 偏粗，影响检索精度
4. **缺少领域验证** — 没有验证"输入 X 应命中 Y 案例"的测试
5. **检索日志字段不足** — 无法回溯分析效果
6. **无 Query 改写** — 用户查询词直接用于检索
7. **无元数据预过滤** — 全量扫描效率低
8. **无 Rerank 模型** — 仅去重合并
9. **关键词检索用 ILIKE** — 未用 PostgreSQL FTS 中文分词

---

## 2. MVP 必须做（Phase 1）

> 目标：让 RAG 检索结果有意义、效果可验证。

### 2.1 切换到真实 Embedding 模型

- 配置 `EMBEDDING_PROVIDER=openai`，`EMBEDDING_MODEL=text-embedding-3-small`
- 支持通过 `EMBEDDING_BASE_URL` 指向任意 OpenAI 兼容端点（如阿里、智谱、本地部署）
- Mock 模式保留为测试用
- **验收标准**：相同语义的文本向量余弦相似度 > 0.8

### 2.2 统一评分权重

- 废弃 router 中的独立评分逻辑，统一调用 `HybridRetriever`
- 权重统一为：`vector=0.4, keyword=0.2, quality=0.2, reuse=0.2`
- 所有评分常量提取为 `HybridRetriever` 的初始化参数，支持配置覆盖
- **验收标准**：router 和 retriever 使用完全相同的评分路径

### 2.3 对齐 Chunk 大小

- 默认值改为 `chunk_size=800, chunk_overlap=100`（spec 500/50 和实现 1000/200 的折中）
- 值通过 `TextChunker.__init__` 参数可配置
- **验收标准**：新文档索引后 chunk 长度中位数 ≤ 800 字符

### 2.4 补齐领域场景验证测试

- 构造测试数据：3D 展示幕墙行业案例（商业综合体裸眼 3D、汽车品牌发布、户外 LED 大屏）
- 编写断言测试：输入特定查询词，验证命中预期案例、验证低质量案例不优先
- 验证 retrieval_logs 完整写入
- **验收标准**：至少 4 个领域场景测试全部通过

---

## 3. MVP 建议做（Phase 2）

> 目标：花较少时间换取明显效果提升。

### 3.1 补全 retrieval_logs 字段

当前模型增加：

| 字段 | 类型 | 说明 |
|------|------|------|
| `structured_query` | JSON | 结构化查询参数（industry, scene, keywords） |
| `retrieved_items` | JSON | 每条结果（id, score, source） |
| `context_pack_summary` | JSON | Context Pack 摘要（cases_count, chunks_count, rules_count） |

### 3.2 元数据预过滤

在 `_vector_search` 和 `_keyword_search` 中增加可选过滤条件：

```python
filters: Optional[dict] = None  # {"industry": "商业地产", "scene": "裸眼3D"}
```

通过 `document_chunks.metadata_json` 或 `cases.industry` 等字段做 WHERE 前置过滤，减少向量计算量。

### 3.3 轻量 Query 扩展

维护一张 `query_synonyms` 配置表：

```json
{"裸眼3D": ["光栅3D", "裸眼立体", "autostereoscopic"], "LED大屏": ["LED幕墙", "LED显示屏", "LED广告屏"]}
```

检索时自动扩展查询词，不需要 LLM 改写。

---

## 4. 后续扩展（Post-MVP）

> 目标：生产级 RAG 精度和评测体系。

### 4.1 Rerank 精排模型

- 引入交叉编码器（CrossEncoder）做精排
- 候选方案：bge-reranker-v2-m3 / Cohere Rerank / 自部署 MiniLM
- 架构预留：`HybridRetriever` 增加 `reranker` 接口，默认 None

```python
class Reranker(ABC):
    async def rerank(self, query: str, results: List[RetrievalResult], top_k: int) -> List[RetrievalResult]: ...

class NoOpReranker(Reranker): ...  # MVP 默认
class CrossEncoderReranker(Reranker): ...  # Post-MVP
```

### 4.2 粗排→精排两阶段

```
粗排：向量召回 top_k=50~100（快速）
  ↓
精排：Rerank 模型重排 top_k=10（精准）
```

### 4.3 PostgreSQL FTS 中文分词

- 安装 zhparser 或 pg_jieba 扩展
- 关键词检索从 ILIKE 升级到 `ts_vector('chinese', ...)` 全文搜索
- 支持中文分词、停用词、权重排序

### 4.4 中文优化 Embedding 模型

- 评估 bge-m3 / BCE / acge 等中文优化模型
- 对比 text-embedding-3-small 在行业数据上的效果
- 支持通过配置切换模型

### 4.5 离线评测框架

- 构建标注数据集（query + 相关文档对）
- 计算指标：MRR / nDCG@K / Hit Rate@K / Recall@K
- 建立基线，每次检索策略变更后跑对比实验
- 详细规格见 `docs/RAG_EVAL_SPEC.md`（待创建）

### 4.6 在线 A/B 测试

- 不同检索策略的效果对比
- 实验分流和统计显著性分析
- 用户隐式反馈（点击、采纳、编辑距离）作为信号

---

## 5. 架构预留接口

以下接口在 MVP 代码中预留，但 Post-MVP 才实现：

```python
# retriever.py 预留
class HybridRetriever:
    def __init__(self, ..., reranker: Optional[Reranker] = None):
        self._reranker = reranker  # MVP: None, Post-MVP: CrossEncoderReranker

    async def search(self, ..., filters: Optional[dict] = None):
        # MVP: filters ignored
        # Post-MVP: apply metadata pre-filtering
        ...
```

```python
# chunker.py 预留
class TextChunker:
    def __init__(self, chunk_size=800, chunk_overlap=100, separator="\n\n"):
        # 参数可配置，不需要改代码
        ...
```

---

## 6. 验收标准总结

| Phase | 验收项 | 指标 |
|-------|--------|------|
| Phase 1 | Embedding 真实可用 | 相似语义余弦 > 0.8 |
| Phase 1 | 评分权重统一 | router 和 retriever 走同一路径 |
| Phase 1 | Chunk 大小合理 | 中位数 ≤ 800 字符 |
| Phase 1 | 领域测试通过 | 4 个场景断言全绿 |
| Phase 2 | 检索日志可追溯 | structured_query + per-item scores 记录完整 |
| Phase 2 | 预过滤生效 | 指定 industry 后结果均匹配 |
| Phase 2 | Query 扩展生效 | 同义词查询命中数提升 |
| Post-MVP | Rerank 上线 | nDCG@10 提升 > 15% |
| Post-MVP | FTS 中文分词 | 中文关键词检索准确率提升 > 20% |
| Post-MVP | 离线评测 | MRR@5 > 0.6, Hit Rate@5 > 0.8 |
