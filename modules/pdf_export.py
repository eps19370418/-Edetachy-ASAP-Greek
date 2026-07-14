from __future__ import annotations

from io import BytesIO
from pathlib import Path
import html
import os
import re
import streamlit as st

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from modules import database


def find_unicode_font() -> str | None:
    bundled = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "DejaVuSans.ttf"
    candidates = [
        str(bundled),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def register_fonts() -> tuple[str, str]:
    latin_greek = "Helvetica"
    path = find_unicode_font()
    if path:
        try:
            pdfmetrics.registerFont(TTFont("EdetachyUnicode", path))
            latin_greek = "EdetachyUnicode"
        except Exception:
            pass

    japanese = "HeiseiKakuGo-W5"
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(japanese))
    except Exception:
        japanese = latin_greek
    return latin_greek, japanese


def is_japanese_char(ch: str) -> bool:
    code = ord(ch)
    return (
        0x3000 <= code <= 0x303F  # Japanese punctuation
        or 0x3040 <= code <= 0x30FF  # Hiragana/Katakana
        or 0x31F0 <= code <= 0x31FF
        or 0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF  # CJK
        or 0xFF00 <= code <= 0xFFEF  # fullwidth
    )


def mixed_markup(text: str, latin_greek: str, japanese: str) -> str:
    """Use a Japanese CID font only for Japanese runs, and DejaVu for Greek/Latin."""
    text = text or ""
    if not text:
        return ""
    runs: list[tuple[bool, str]] = []
    current_kind = is_japanese_char(text[0])
    current = [text[0]]
    for ch in text[1:]:
        kind = is_japanese_char(ch)
        if kind == current_kind:
            current.append(ch)
        else:
            runs.append((current_kind, "".join(current)))
            current_kind = kind
            current = [ch]
    runs.append((current_kind, "".join(current)))
    return "".join(
        f'<font name="{japanese if jp else latin_greek}">{html.escape(run)}</font>'
        for jp, run in runs
    )


def build_pdf(category: str, rows: list[dict], title: str) -> bytes:
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=title,
    )
    latin_greek, japanese = register_fonts()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleCustom",
        parent=styles["Title"],
        fontName=latin_greek,
        fontSize=18,
        leading=22,
        spaceAfter=8,
    )
    cell = ParagraphStyle(
        "Cell",
        parent=styles["BodyText"],
        fontName=latin_greek,
        fontSize=8.5,
        leading=10.5,
        alignment=TA_LEFT,
    )

    def p(text: str) -> Paragraph:
        return Paragraph(mixed_markup(str(text), latin_greek, japanese), cell)

    story = [Paragraph(html.escape(title), title_style), Spacer(1, 4)]

    if category == "vocab":
        headers = ["#", "Greek", "Meaning", "Hint"]
        data = [[str(r["rank"]), p(r["greek"]), p(r["meaning"]), p(r.get("hint", ""))] for r in rows]
        widths = [10 * mm, 35 * mm, 54 * mm, 82 * mm]
    elif category == "aorist":
        headers = ["#", "Present", "Aorist", "Meaning"]
        data = [[str(r["rank"]), p(r["present"]), p(r["aorist"]), p(r.get("meaning", ""))] for r in rows]
        widths = [10 * mm, 48 * mm, 48 * mm, 75 * mm]
    else:
        headers = ["#", "Present", "Present participle", "Aorist participle", "Meaning"]
        data = [[
            str(r["rank"]), p(r["present"]), p(r["present_participle"]),
            p(r["aorist_participle"]), p(r.get("meaning", ""))
        ] for r in rows]
        widths = [9 * mm, 36 * mm, 45 * mm, 45 * mm, 46 * mm]

    table = Table([headers] + data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), latin_greek),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d8c4a0")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#2c2117")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#7b6a54")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f1e7")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table)
    doc.build(story)
    return output.getvalue()


def render(db_path: Path, user_id: int, lang: str) -> None:
    st.subheader("PDF出力" if lang == "ja" else "PDF exports")
    category_labels = {
        "vocab": "単語" if lang == "ja" else "Vocabulary",
        "aorist": "アオリスト" if lang == "ja" else "Aorist",
        "participle": "分詞" if lang == "ja" else "Participles",
    }
    selected_label = st.selectbox(
        "カテゴリ" if lang == "ja" else "Category",
        list(category_labels.values()),
        key="pdf_export_category",
    )
    category = next(k for k, v in category_labels.items() if v == selected_label)

    full_rows = database.cards_for_export(db_path, user_id, category)
    known_rows = database.cards_for_export(db_path, user_id, category, "known")

    full_pdf = build_pdf(category, full_rows, f"Edetachy ASAP - {category_labels[category]}")
    known_pdf = build_pdf(
        category,
        known_rows,
        f"Edetachy ASAP - {category_labels[category]} - {'覚えた' if lang == 'ja' else 'Known'}",
    )

    st.download_button(
        "全体一覧PDF" if lang == "ja" else "Download full list PDF",
        data=full_pdf,
        file_name=f"edetachy_{category}_all.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
    st.download_button(
        "「覚えた」一覧PDF" if lang == "ja" else "Download known-only PDF",
        data=known_pdf,
        file_name=f"edetachy_{category}_known.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
