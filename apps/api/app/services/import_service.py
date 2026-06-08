"""ImportService — parse uploaded files into entity creation dicts."""
import csv
import io
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from fastapi import UploadFile

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    imported: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)
    items: list[dict] = field(default_factory=list)


class ImportService:
    """Parse uploaded files into entity-ready dicts for DB insertion."""

    # Allowed extensions per entity type
    ENTITY_EXTENSIONS = {
        "case": {".json", ".csv"},
        "sop_workflow": {".json"},
        "proposal_template": {".json"},
        "prompt_template": {".json", ".txt", ".md"},
        "visual_style": {".json"},
        "technical_rule": {".json", ".txt"},
        "quality_rule": {".json", ".txt"},
    }

    @classmethod
    async def parse_file(cls, file: UploadFile, entity_type: str) -> ImportResult:
        """Parse an uploaded file into entity-ready dicts."""
        ext = cls._get_extension(file.filename or "")
        allowed = cls.ENTITY_EXTENSIONS.get(entity_type, {".json"})
        if ext not in allowed:
            return ImportResult(
                failed=1,
                errors=[f"不支持的文件格式 '{ext}'，允许: {', '.join(sorted(allowed))}"],
            )

        # Read file content
        content = await file.read()
        text = content.decode("utf-8-sig")  # utf-8-sig handles BOM

        if not text.strip():
            return ImportResult(failed=1, errors=["文件内容为空"])

        try:
            if ext == ".json":
                items = cls._parse_json(text)
            elif ext == ".csv":
                items = cls._parse_csv(text)
            elif ext in (".txt", ".md"):
                items = cls._parse_text(text, entity_type)
            else:
                return ImportResult(failed=1, errors=[f"无法解析 '{ext}' 格式"])
        except Exception as e:
            return ImportResult(failed=1, errors=[f"文件解析失败: {str(e)}"])

        # Validate items
        result = ImportResult()
        for i, item in enumerate(items):
            try:
                validated = cls._validate_item(item, entity_type)
                result.items.append(validated)
                result.imported += 1
            except ValueError as e:
                result.failed += 1
                result.errors.append(f"第 {i+1} 条: {str(e)}")

        return result

    @staticmethod
    def _get_extension(filename: str) -> str:
        """Extract lowercase extension from filename."""
        if "." not in filename:
            return ""
        return "." + filename.rsplit(".", 1)[-1].lower()

    @staticmethod
    def _parse_json(text: str) -> list[dict]:
        """Parse JSON text into a list of dicts."""
        data = json.loads(text)
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return data
        raise ValueError("JSON 必须是对象或数组")

    @staticmethod
    def _parse_csv(text: str) -> list[dict]:
        """Parse CSV text into a list of dicts."""
        reader = csv.DictReader(io.StringIO(text))
        items = []
        for row in reader:
            # Filter out None values and empty strings
            item = {k: v for k, v in row.items() if k and v}
            if item:
                items.append(item)
        return items

    @classmethod
    def _parse_text(cls, text: str, entity_type: str) -> list[dict]:
        """Parse plain text into items based on entity type."""
        if entity_type == "prompt_template":
            return cls._parse_text_template(text)
        elif entity_type in ("technical_rule", "quality_rule"):
            return cls._parse_text_rules(text)
        raise ValueError(f"不支持文本格式导入 '{entity_type}'")

    @staticmethod
    def _parse_text_template(text: str) -> list[dict]:
        """Parse text as a prompt template. First line = name, rest = template_text."""
        lines = text.strip().split("\n")
        if not lines:
            raise ValueError("文件内容为空")

        name = lines[0].strip()
        template_text = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

        if not name:
            raise ValueError("首行不能为空（用作模板名称）")

        # Extract {{variable}} patterns
        variables = re.findall(r'\{\{(\w+)\}\}', template_text)

        return [{
            "name": name,
            "template_text": template_text or name,
            "variables": list(set(variables)),
            "category": "imported",
            "description": f"从文件导入: {name}",
        }]

    @staticmethod
    def _parse_text_rules(text: str) -> list[dict]:
        """Parse text as rules. Sections separated by blank lines. First line = name."""
        sections = re.split(r'\n\s*\n', text.strip())
        items = []
        for section in sections:
            section = section.strip()
            if not section:
                continue
            lines = section.split("\n")
            name = lines[0].strip()
            rule_text = "\n".join(lines[1:]).strip() if len(lines) > 1 else name
            if not name:
                continue
            items.append({
                "name": name,
                "rule_text": rule_text,
                "category": "imported",
                "description": f"从文件导入: {name}",
            })
        return items

    @staticmethod
    def _validate_item(item: dict, entity_type: str) -> dict:
        """Validate and normalize an item for the given entity type."""
        validators = {
            "case": ImportService._validate_case,
            "sop_workflow": ImportService._validate_sop_workflow,
            "proposal_template": ImportService._validate_proposal_template,
            "prompt_template": ImportService._validate_prompt_template,
            "visual_style": ImportService._validate_visual_style,
            "technical_rule": ImportService._validate_technical_rule,
            "quality_rule": ImportService._validate_quality_rule,
        }
        validator = validators.get(entity_type)
        if validator:
            return validator(item)
        return item

    @staticmethod
    def _validate_case(item: dict) -> dict:
        if not item.get("title"):
            raise ValueError("案例标题 (title) 不能为空")
        if not item.get("client_name"):
            raise ValueError("客户名称 (client_name) 不能为空")
        # Convert numeric fields
        for key in ("team_size",):
            if key in item and isinstance(item[key], str):
                try:
                    item[key] = int(item[key])
                except ValueError:
                    del item[key]
        if "quality_score" in item and isinstance(item["quality_score"], str):
            try:
                item["quality_score"] = float(item["quality_score"])
            except ValueError:
                del item["quality_score"]
        return item

    @staticmethod
    def _validate_sop_workflow(item: dict) -> dict:
        if not item.get("name"):
            raise ValueError("SOP 名称 (name) 不能为空")
        return item

    @staticmethod
    def _validate_proposal_template(item: dict) -> dict:
        if not item.get("name"):
            raise ValueError("模板名称 (name) 不能为空")
        if not item.get("category"):
            item["category"] = "imported"
        return item

    @staticmethod
    def _validate_prompt_template(item: dict) -> dict:
        if not item.get("name"):
            raise ValueError("模板名称 (name) 不能为空")
        if not item.get("template_text"):
            raise ValueError("模板文本 (template_text) 不能为空")
        if not item.get("category"):
            item["category"] = "imported"
        return item

    @staticmethod
    def _validate_visual_style(item: dict) -> dict:
        if not item.get("name"):
            raise ValueError("风格名称 (name) 不能为空")
        return item

    @staticmethod
    def _validate_technical_rule(item: dict) -> dict:
        if not item.get("name"):
            raise ValueError("规则名称 (name) 不能为空")
        if not item.get("rule_text"):
            raise ValueError("规则内容 (rule_text) 不能为空")
        if not item.get("category"):
            item["category"] = "imported"
        return item

    @staticmethod
    def _validate_quality_rule(item: dict) -> dict:
        if not item.get("name"):
            raise ValueError("规则名称 (name) 不能为空")
        if not item.get("rule_text"):
            raise ValueError("规则内容 (rule_text) 不能为空")
        if not item.get("category"):
            item["category"] = "imported"
        # Convert weight
        if "weight" in item and isinstance(item["weight"], str):
            try:
                item["weight"] = float(item["weight"])
            except ValueError:
                item["weight"] = 1.0
        return item
