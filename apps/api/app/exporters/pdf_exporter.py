"""PDF export functionality."""

import os
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings


class PDFExporter:
    """Export content to PDF format using ReportLab."""

    async def export(
        self,
        content: str,
        filename: str,
        title: Optional[str] = None,
        author: str = "3D Wall Platform",
    ) -> str:
        """Export markdown-like content to a PDF document.

        Returns the file path of the generated PDF.
        """
        from reportlab.lib.colors import HexColor
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        storage_dir = os.path.abspath(settings.storage_path)
        os.makedirs(storage_dir, exist_ok=True)
        filepath = os.path.join(storage_dir, filename)

        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
            title=title or filename,
            author=author,
        )

        styles = getSampleStyleSheet()

        # Custom styles
        styles.add(
            ParagraphStyle(
                name="CustomH1",
                parent=styles["Heading1"],
                fontSize=22,
                textColor=HexColor("#1a73e8"),
                spaceAfter=16,
                spaceBefore=24,
            )
        )
        styles.add(
            ParagraphStyle(
                name="CustomH2",
                parent=styles["Heading2"],
                fontSize=16,
                textColor=HexColor("#333333"),
                spaceAfter=12,
                spaceBefore=18,
            )
        )
        styles.add(
            ParagraphStyle(
                name="CustomH3",
                parent=styles["Heading3"],
                fontSize=13,
                textColor=HexColor("#444444"),
                spaceAfter=8,
                spaceBefore=12,
            )
        )
        styles.add(
            ParagraphStyle(
                name="BodyText2",
                parent=styles["Normal"],
                fontSize=11,
                leading=16,
                spaceAfter=8,
            )
        )

        story = []

        for line in content.split("\n"):
            stripped = line.strip()
            if not stripped:
                story.append(Spacer(1, 0.15 * inch))
            elif stripped.startswith("# "):
                story.append(Paragraph(_escape(stripped[2:]), styles["CustomH1"]))
            elif stripped.startswith("## "):
                story.append(Paragraph(_escape(stripped[3:]), styles["CustomH2"]))
            elif stripped.startswith("### "):
                story.append(Paragraph(_escape(stripped[4:]), styles["CustomH3"]))
            elif stripped.startswith("#### "):
                story.append(Paragraph(_escape(stripped[5:]), styles["Heading4"]))
            elif stripped.startswith("- ") or stripped.startswith("* "):
                safe = _escape(stripped[2:])
                story.append(Paragraph(f"&bull; {safe}", styles["BodyText2"]))
            elif stripped.startswith("---"):
                story.append(Spacer(1, 0.1 * inch))
            elif stripped.startswith("| "):
                # Table row — extract cells
                cells = [c.strip() for c in stripped.split("|")[1:-1]]
                if cells:
                    # Check if separator row
                    if all(set(c.strip()) <= {"-", ":"} for c in cells if c.strip()):
                        continue
                    safe_cells = [_escape(c) for c in cells]
                    t = Table([safe_cells])
                    t.setStyle(TableStyle([
                        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]))
                    story.append(t)
            else:
                safe = _escape(stripped)
                story.append(Paragraph(safe, styles["BodyText2"]))

        # Footer
        story.append(Spacer(1, 0.5 * inch))
        footer_text = (
            f"Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
            f" by {author}"
        )
        story.append(Paragraph(footer_text, styles["Italic"]))

        doc.build(story)
        return filepath


def _escape(text: str) -> str:
    """Escape HTML special characters for ReportLab Paragraph."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
