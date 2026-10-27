"""Import Knowledge Pack ZIP (documents, cases, talking points, eval_set)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
import uuid
import zipfile
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.models.app_setting import AppSetting
from app.models.case import Case
from app.models.talking_point import TalkingPoint
from app.services.document_service import DocumentService
from app.services.eval_service import eval_service

logger = logging.getLogger(__name__)

REGISTRY_KEY = "knowledge_pack_registry"

DOC_CATEGORY_MAP = {
    "product": "产品资料",
    "handbook": "产品资料",
    "technical": "技术资料",
    "company": "企业介绍",
    "case": "案例资料",
    "faq": "其他资料",
}

PACK_TEMPLATES = [
    {
        "template_id": "b2b-smoke-v1",
        "description": "ZIP 内含 knowledge_pack.json + files/ 文档",
        "format_hint": "见 KB_PRIVATE_DELIVERY_SPEC §19",
    },
]


class KnowledgePackService:
    def __init__(self) -> None:
        self._documents = DocumentService(storage_path=settings.storage_path)

    async def list_templates(self) -> List[Dict[str, str]]:
        return list(PACK_TEMPLATES)

    async def _load_registry(self, db: AsyncSession) -> Dict[str, str]:
        row = (
            await db.execute(select(AppSetting).where(AppSetting.key == REGISTRY_KEY))
        ).scalar_one_or_none()
        if not row or not row.value:
            return {}
        try:
            return json.loads(row.value)
        except json.JSONDecodeError:
            return {}

    async def _save_registry(self, db: AsyncSession, registry: Dict[str, str]) -> None:
        row = (
            await db.execute(select(AppSetting).where(AppSetting.key == REGISTRY_KEY))
        ).scalar_one_or_none()
        payload = json.dumps(registry, ensure_ascii=False)
        if row:
            row.value = payload
        else:
            db.add(AppSetting(key=REGISTRY_KEY, value=payload))
        await db.flush()

    async def import_zip(
        self,
        db: AsyncSession,
        zip_bytes: bytes,
        *,
        project_id: Optional[uuid.UUID] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        content_hash = hashlib.sha256(zip_bytes).hexdigest()
        errors: List[str] = []
        documents_imported = 0
        cases_imported = 0
        talking_points_imported = 0
        eval_set_id: Optional[uuid.UUID] = None
        pack_name = "unknown"

        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "pack.zip")
            with open(zip_path, "wb") as f:
                f.write(zip_bytes)

            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(tmp)
            except zipfile.BadZipFile as exc:
                raise BadRequestException("无效的 ZIP 文件") from exc

            manifest_path = os.path.join(tmp, "knowledge_pack.json")
            if not os.path.isfile(manifest_path):
                raise BadRequestException("ZIP 内缺少 knowledge_pack.json")

            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)

            pack_name = str(manifest.get("name") or "unnamed-pack")
            registry = await self._load_registry(db)
            if not force and registry.get(pack_name) == content_hash:
                return {
                    "pack_name": pack_name,
                    "documents_imported": 0,
                    "cases_imported": 0,
                    "talking_points_imported": 0,
                    "eval_set_id": None,
                    "skipped": True,
                    "errors": [],
                }

            default_project_id = project_id
            if default_project_id is None:
                pid_raw = manifest.get("default_project_id")
                if pid_raw:
                    default_project_id = uuid.UUID(str(pid_raw))

            for doc_meta in manifest.get("documents") or []:
                try:
                    rel = doc_meta.get("relative_path") or doc_meta.get("path")
                    if not rel:
                        errors.append("document 缺少 relative_path")
                        continue
                    src = os.path.join(tmp, rel)
                    if not os.path.isfile(src):
                        errors.append(f"文件不存在: {rel}")
                        continue
                    doc_project = doc_meta.get("project_id")
                    doc_pid = (
                        uuid.UUID(str(doc_project))
                        if doc_project
                        else default_project_id
                    )
                    category = DOC_CATEGORY_MAP.get(
                        str(doc_meta.get("doc_category") or "").lower(),
                        "其他资料",
                    )
                    title = doc_meta.get("title") or os.path.basename(rel)
                    original = os.path.basename(rel)
                    await self._documents.import_file_from_path(
                        src,
                        original_filename=original,
                        db=db,
                        project_id=doc_pid,
                        title=title,
                        category=category,
                        auto_index=True,
                    )
                    documents_imported += 1
                except Exception as exc:
                    logger.exception("pack document import failed")
                    errors.append(f"document {doc_meta.get('title', rel)}: {exc}"[:200])

            if default_project_id is None and (manifest.get("cases") or []):
                errors.append("cases 需要 project_id（导入参数或 manifest.default_project_id）")
            else:
                for case_item in manifest.get("cases") or []:
                    try:
                        title = case_item.get("title") or "导入案例"
                        case = Case(
                            project_id=default_project_id,
                            title=title,
                            client_name=case_item.get("client_name") or "导入",
                            industry=case_item.get("industry"),
                            tags=case_item.get("tags"),
                            solution=case_item.get("solution_summary")
                            or case_item.get("solution"),
                            challenge=case_item.get("challenge"),
                            is_published=bool(case_item.get("is_published", False)),
                        )
                        db.add(case)
                        cases_imported += 1
                    except Exception as exc:
                        errors.append(f"case {case_item.get('title')}: {exc}"[:200])
                await db.flush()

            for tp in manifest.get("talking_points") or []:
                try:
                    scene = tp.get("scene") or tp.get("scenario") or "通用"
                    row = TalkingPoint(
                        scenario=scene,
                        title=tp.get("title") or scene,
                        content=tp.get("content"),
                        industry=tp.get("industry"),
                        tags=tp.get("tags"),
                        is_active=tp.get("is_active", True),
                    )
                    db.add(row)
                    talking_points_imported += 1
                except Exception as exc:
                    errors.append(f"talking_point: {exc}"[:200])
            await db.flush()

            eval_block = manifest.get("eval_set")
            if eval_block:
                try:
                    es = await eval_service.create_set(
                        db,
                        name=str(eval_block.get("name") or f"{pack_name}-eval"),
                        description=eval_block.get("description"),
                        project_id=default_project_id,
                    )
                    for ec in eval_block.get("cases") or []:
                        await eval_service.create_case(
                            db,
                            es.id,
                            {
                                "query": ec["query"],
                                "expected_keywords": ec.get("expected_keywords", []),
                                "expected_chunk_ids": ec.get("expected_chunk_ids", []),
                                "notes": ec.get("notes"),
                                "source": "pack",
                            },
                        )
                    eval_set_id = es.id
                except Exception as exc:
                    errors.append(f"eval_set: {exc}"[:200])

            registry[pack_name] = content_hash
            await self._save_registry(db, registry)

        return {
            "pack_name": pack_name,
            "documents_imported": documents_imported,
            "cases_imported": cases_imported,
            "talking_points_imported": talking_points_imported,
            "eval_set_id": eval_set_id,
            "skipped": False,
            "errors": errors,
        }


knowledge_pack_service = KnowledgePackService()
