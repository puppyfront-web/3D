"""Auto-tagging service — LLM-suggested tags and categories for knowledge assets.

Uses a lightweight LLM call to suggest industry tags and content categories
for imported knowledge materials (cases, documents, SOPs, etc.).
Best-effort: degrades to empty suggestions on any failure.
"""
import logging
from typing import Dict

from app.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)

# The 9 attachment categories (PRD §11.2)
ATTACHMENT_CATEGORIES = [
    "企业介绍", "产品资料", "技术资料", "荣誉资质",
    "案例资料", "发展历程", "社会责任", "参考案例", "其他资料",
]

# The canonical industries
INDUSTRIES = [
    "智慧城市", "工业制造", "金融科技", "能源电力",
    "政务", "科技", "汽车", "商业综合体", "文旅", "通用",
]


async def suggest_tags(
    db, entity_type: str, content: str, title: str = ""
) -> Dict:
    """Suggest tags, category, and industry for a knowledge asset.

    Returns: {"tags": [...], "category": "...", "industry": "...", "confidence": 0.0-1.0}
    Never raises — returns empty suggestions on failure.
    """
    empty = {"tags": [], "category": None, "industry": None, "confidence": 0.0}

    if not content or len(content) < 10:
        return empty

    try:
        llm = await get_llm_service(db)
        prompt = (
            f"分析以下知识库内容，返回 JSON：\n"
            '{"tags": ["标签1", "标签2"], "category": "分类", "industry": "行业"}\n\n'
            f"标题：{title or '（无）'}\n"
            f"内容（前500字）：{content[:500]}\n\n"
            "标签规则：\n"
            f"1. tags：3-5个关键词标签，提取内容中的核心主题。\n"
            f"2. category：从以下选一个最匹配的：{', '.join(ATTACHMENT_CATEGORIES)}\n"
            f"3. industry：从以下选一个最匹配的：{', '.join(INDUSTRIES)}\n"
            "只返回 JSON，不要其他文字。"
        )
        result = await llm.generate_json(prompt, temperature=0.2)
        if not result or not isinstance(result, dict):
            return empty

        tags = result.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        tags = [str(t) for t in tags if t][:5]

        category = result.get("category")
        if category and category not in ATTACHMENT_CATEGORIES:
            category = None  # Only accept known categories

        industry = result.get("industry")
        if industry and industry not in INDUSTRIES:
            industry = None

        return {"tags": tags, "category": category, "industry": industry, "confidence": 0.8}
    except Exception as e:
        logger.warning("Auto-tagging failed for %s: %s", entity_type, e)
        return empty
