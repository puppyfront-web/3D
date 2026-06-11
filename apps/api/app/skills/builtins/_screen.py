"""Shared screen / venue parameter rendering for the proposal & visual skills.

Both skills render the project's ``screen_info`` (尺寸/类型/点距/安装环境/观看距离
…) into their prompts. The label map and the empty-vs-populated branching are
identical; only the intro/tail wording differs. Centralizing it keeps the two
skills from drifting and is the single place to add a new screen field.
"""

from typing import Any, List

# Chinese labels for the canonical screen-info fields. Keys match the
# ScreenInfo schema (snake_case) stored on Project.screen_info.
SCREEN_LABELS = {
    "screen_type": "屏幕类型",
    "screen_size": "屏幕尺寸",
    "pitch": "点距",
    "resolution": "分辨率",
    "install_environment": "安装环境",
    "viewing_distance": "观看距离",
    "main_viewpoint": "主观看点",
    "notes": "备注",
}


def render_screen_block(
    screen_info: Any,
    intro: str,
    empty_marker: str,
    tail: str = "",
) -> str:
    """Render screen params as a labeled list.

    Returns ``empty_marker`` when ``screen_info`` is missing/empty (the caller
    phrases it so the LLM marks the params 待确认 instead of fabricating them).
    Otherwise returns ``intro`` + one labeled row per provided field + ``tail``.
    """
    if not screen_info or not isinstance(screen_info, dict):
        return empty_marker
    rows = [f"  - {SCREEN_LABELS.get(k, k)}：{v}" for k, v in screen_info.items() if v]
    if not rows:
        return empty_marker
    return intro + "\n" + "\n".join(rows) + tail


def missing_screen_labels(screen_info: Any) -> List[str]:
    """Chinese labels of screen params absent from ``screen_info``."""
    provided = set()
    if isinstance(screen_info, dict):
        provided = {SCREEN_LABELS.get(k, k) for k, v in screen_info.items() if v}
    return sorted(set(SCREEN_LABELS.values()) - provided)
