"""One-off: generate the landing hero illustration via the platform's own
image service (dogfooding the admin-configured provider). Saves to
apps/web/public/images/hero-team-discussion.png.

Run from apps/api:  python scripts/generate_hero_art.py
"""

import asyncio
import sys
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[2] / "web" / "public" / "images" / "hero-team-discussion.png"

PROMPT = (
    "Minimal flat vector illustration, dark tech product landing page art. "
    "Near-black background (#010102). A round-table scene viewed slightly from above: "
    "in the center a glowing lavender-blue AI brain character acting as CEO "
    "(#5E6AD2), around it three smaller friendly robot-agent characters in dark charcoal "
    "shades (#0F1011, #141516) with thin lavender outlines, engaged in a discussion. "
    "Thin glowing connection lines link the CEO brain to each agent. Floating UI panels, "
    "checklists and chart fragments hover around the table in dark charcoal cards with "
    "hairline borders and small lavender accent dots. Subtle lavender glow, generous "
    "negative space, premium SaaS aesthetic like Linear.app marketing art. "
    "Absolutely no text, no letters, no words, no numbers anywhere."
)


async def main() -> None:
    from app.db.session import async_session_factory
    from app.services.image_service import get_image_service

    async with async_session_factory() as db:
        service = await get_image_service(db)
        data = await service.generate_image(PROMPT, width=1536, height=1024)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(data)
    print(f"saved {len(data)} bytes -> {OUTPUT}")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
