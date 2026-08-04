"""Canvas → Markdown flattener for document export (PRD §20).

Takes a ProjectVersion + its Canvas (with groups, nodes, and each node's
sources) and produces a single markdown string ordered by the three board
sections. Source provenance and pending-question markers are inline so the
exported document stays traceable — a soft gate (PRD §20.3): draft /
pending nodes are not blocked, but flagged with ⚠️ markers.

This is the adapter that lets WordExporter / PDFExporter (which only accept
a `content: str`) work off the canvas version without any change to them.
"""

from typing import Any, Dict, List, Optional

# Board-group export order (matches canvas_service._DEFAULT_GROUPS). Defined
# locally to avoid importing the service layer here — this module stays a
# pure function over ORM objects.
_GROUP_ORDER = [
    "company_intro",
    "product_tech_scenarios",
    "future_social_responsibility",
]


def _fmt_slot(items: Any) -> List[str]:
    """Render a node content slot (list/scalar) as a list of bullet lines."""
    if not items:
        return []
    if isinstance(items, list):
        out: List[str] = []
        for it in items:
            if isinstance(it, dict):
                txt = it.get("text") or it.get("detail") or it.get("title") or ""
                if txt:
                    out.append(str(txt))
                else:
                    out.append(str(it))
            else:
                out.append(str(it))
        return out
    return [str(items)]


def _fmt_sources(sources: List[Any]) -> str:
    """Format a node's NodeSource list as a single '来源：…' line."""
    if not sources:
        return ""
    parts = []
    for s in sources[:5]:
        name = getattr(s, "source_name", None) or getattr(s, "source_type", "?")
        stype = getattr(s, "source_type", "")
        conf = getattr(s, "confidence", None) or "—"
        parts.append(f"{name}（{stype}, {conf}）")
    return "来源：" + ", ".join(parts)


def canvas_to_markdown(
    version: Any,
    canvas: Any,
    include_drafts: bool = True,
) -> str:
    """Flatten a version's canvas into a markdown document.

    Args:
        version: ProjectVersion ORM row (uses version_name / change_summary).
        canvas: Canvas ORM row with `groups` and `nodes` relationships loaded
                (each node should have `sources` loaded too).
        include_drafts: when False, skip nodes whose status == 'draft'.

    Returns:
        A markdown string ordered by the three board sections.
    """
    version_name = getattr(version, "version_name", None) or f"V{getattr(version, 'version_no', '?')}"
    change_summary = getattr(version, "change_summary", None) or ""

    # Index groups by group_key for ordered output.
    groups_by_key: Dict[str, Any] = {g.group_key: g for g in (canvas.groups or [])}

    # Index nodes by their group_id so we can place each under its group.
    nodes_by_group: Dict[Any, List[Any]] = {}
    for node in (canvas.nodes or []):
        nodes_by_group.setdefault(node.group_id, []).append(node)

    lines: List[str] = []
    lines.append(f"# 企业3D数字化整体解决方案（{version_name}）")
    lines.append("")
    if change_summary:
        lines.append(f"> {change_summary}")
        lines.append("")

    for group_key in _GROUP_ORDER:
        group = groups_by_key.get(group_key)
        if group is None:
            continue
        lines.append(f"## {group.title}")
        if group.description:
            lines.append(f"*{group.description}*")
        lines.append("")

        group_nodes = nodes_by_group.get(group.id, [])
        # Stable order: by node_key (falls back to title).
        group_nodes.sort(key=lambda n: getattr(n, "node_key", None) or "")

        for node in group_nodes:
            if not include_drafts and (node.status or "") == "draft":
                continue
            title = node.title or node.node_key or "节点"
            lines.append(f"### {title}")

            content = node.content or {}
            planning = _fmt_slot(content.get("planning"))
            extracted = _fmt_slot(content.get("extracted"))
            pending = _fmt_slot(content.get("pending_questions"))

            status = node.status or "draft"
            is_incomplete = status in ("draft", "filling", "pending_review") or not planning

            if planning:
                for item in planning:
                    lines.append(f"- {item}")
            else:
                lines.append("- （暂无内容）")

            # Source provenance (traceability, PRD §4.5).
            src_line = _fmt_sources(node.sources or [])
            if src_line:
                lines.append("")
                lines.append(f"> {src_line}")

            # Soft-gate markers (PRD §20.3): don't block, but flag.
            if pending:
                lines.append("")
                for p in pending:
                    lines.append(f"> ⚠️ 待确认：{p}")
            if is_incomplete and status != "filled":
                marker = {
                    "draft": "待补充",
                    "filling": "生成中",
                    "pending_review": "待人工确认",
                }.get(status, "待补充")
                lines.append("")
                lines.append(f"> ⚠️ 节点状态：{marker}")

            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*本文档由售前方案工作台自动生成，AI 补全内容请人工核实后使用。*")
    return "\n".join(lines)
