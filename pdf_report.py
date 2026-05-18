"""
pdf_report.py
=============

CCUS 벤치마크 도구 — PDF 리포트 생성 모듈.

ReportLab + Platypus로 다중 페이지 PDF를 만든다.
중요 규칙 (PDF SKILL.md 준수):
  - subscript/superscript는 Unicode 쓰지 말고 <sub>/<super> 태그 사용
  - CO₂ → CO<sub>2</sub>, GJ/tCO₂ → GJ/tCO<sub>2</sub>
  - 한글은 ReportLab 기본 폰트 미지원 → Helvetica는 영문/숫자/기본기호만 안전
  - 한글이 필요하면 ASCII 라벨로 옮기고 한글은 captions에 분리

사용:
    from pdf_report import build_pdf_report
    pdf_bytes = build_pdf_report(results, meta_dict, fx_krw_per_usd)
    st.download_button("📥 PDF", data=pdf_bytes, file_name="ccus_report.pdf")
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ─────────────────────────────────────────────────────────────
# Color palette (matches Streamlit dark theme accents)
# ─────────────────────────────────────────────────────────────
ACCENT_GREEN = colors.HexColor("#2E7D32")
ACCENT_BLUE = colors.HexColor("#1565C0")
ACCENT_GRAY = colors.HexColor("#37474F")
ACCENT_ORANGE = colors.HexColor("#EF6C00")
ROW_ALT = colors.HexColor("#ECEFF1")
HEADER_BG = colors.HexColor("#263238")
HEADER_FG = colors.white
PROFIT_GREEN = colors.HexColor("#1B5E20")
LOSS_RED = colors.HexColor("#B71C1C")
SUBTLE = colors.HexColor("#90A4AE")


# ─────────────────────────────────────────────────────────────
# Styles
# ─────────────────────────────────────────────────────────────
def _build_styles():
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "title", parent=base["Title"],
            fontName="Helvetica-Bold", fontSize=18, leading=22,
            alignment=TA_LEFT, textColor=ACCENT_BLUE, spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"],
            fontName="Helvetica", fontSize=10, leading=13,
            textColor=ACCENT_GRAY, spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"],
            fontName="Helvetica-Bold", fontSize=12, leading=15,
            textColor=ACCENT_BLUE, spaceBefore=10, spaceAfter=4,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"],
            fontName="Helvetica-Bold", fontSize=10.5, leading=13,
            textColor=ACCENT_GRAY, spaceBefore=6, spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontName="Helvetica", fontSize=9, leading=12,
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"],
            fontName="Helvetica", fontSize=8, leading=10,
            textColor=ACCENT_GRAY,
        ),
        "footer": ParagraphStyle(
            "footer", parent=base["Normal"],
            fontName="Helvetica-Oblique", fontSize=7.5, leading=10,
            textColor=SUBTLE,
        ),
        "kpi_big": ParagraphStyle(
            "kpi_big", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=16, leading=18,
            alignment=TA_CENTER,
        ),
        "kpi_label": ParagraphStyle(
            "kpi_label", parent=base["Normal"],
            fontName="Helvetica", fontSize=8, leading=10,
            alignment=TA_CENTER, textColor=ACCENT_GRAY,
        ),
    }
    return styles


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _safe_num(x, default=0.0):
    try:
        if x is None:
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def _fmt_money_usd(usd: float) -> str:
    """E.g. -1.23M, +25.4M, -156k"""
    if abs(usd) >= 1e9:
        return f"${usd/1e9:+,.2f}B"
    if abs(usd) >= 1e6:
        return f"${usd/1e6:+,.2f}M"
    if abs(usd) >= 1e3:
        return f"${usd/1e3:+,.1f}k"
    return f"${usd:+,.0f}"


def _fmt_money_krw(krw: float) -> str:
    """KRW abbreviation. Helvetica-safe (ASCII only) — never use Korean glyphs here."""
    if abs(krw) >= 1e12:   # 조 (trillion) — was "조원" which renders as black boxes in Helvetica
        return f"{krw/1e12:+,.2f}T-KRW"
    if abs(krw) >= 1e8:    # 억 (100M)
        return f"{krw/1e8:+,.1f}eok-won"
    if abs(krw) >= 1e4:    # 만 (10K)
        return f"{krw/1e4:+,.0f}man-won"
    return f"{krw:+,.0f}KRW"


def _profit_color(usd: float):
    return PROFIT_GREEN if usd >= 0 else LOSS_RED


# ─────────────────────────────────────────────────────────────
# Plotly figure → PNG bytes (optional — kaleido must be installed)
# ─────────────────────────────────────────────────────────────
def fig_to_png_bytes(fig, width=900, height=400, scale=1.6) -> bytes | None:
    """Convert Plotly figure to PNG. Returns None if kaleido missing."""
    try:
        return fig.to_image(format="png", width=width, height=height, scale=scale)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# Page header / footer
# ─────────────────────────────────────────────────────────────
def _on_page(canvas_, doc):
    """Draw header & footer on every page."""
    canvas_.saveState()
    page_w, page_h = A4

    # Top header bar
    canvas_.setFillColor(HEADER_BG)
    canvas_.rect(0, page_h - 14 * mm, page_w, 14 * mm, fill=True, stroke=False)
    canvas_.setFillColor(HEADER_FG)
    canvas_.setFont("Helvetica-Bold", 10)
    canvas_.drawString(15 * mm, page_h - 9 * mm,
                        "CCUS Tech-Economic Benchmark Report")
    canvas_.setFont("Helvetica", 8)
    canvas_.drawRightString(page_w - 15 * mm, page_h - 9 * mm,
                              datetime.now().strftime("%Y-%m-%d %H:%M"))

    # Footer
    canvas_.setFillColor(SUBTLE)
    canvas_.setFont("Helvetica-Oblique", 7.5)
    canvas_.drawString(15 * mm, 8 * mm,
                        "(c) 2026 Song BK · MIT License · github.com/cafeon90-oss")
    canvas_.setFont("Helvetica", 7.5)
    canvas_.drawRightString(page_w - 15 * mm, 8 * mm,
                              f"Page {doc.page}")
    canvas_.restoreState()


# ─────────────────────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────────────────────
def _build_meta_card(meta: dict, styles) -> Table:
    """Top metadata card — facility mode, capture, scenarios, etc."""
    rows = [
        ["Facility mode", meta.get("facility_mode", "—")],
        ["Project scenario", str(meta.get("project_scenario", "—"))],
        ["Capture rate [Mt/yr]", f"{_safe_num(meta.get('capture_mt_yr')):,.2f}"],
        ["Carbon market", str(meta.get("cm_select", "—"))],
        ["Subsidy", str(meta.get("sub_select", "—"))],
        ["FX [KRW/USD]", f"{_safe_num(meta.get('fx', 1380)):,.0f}"],
        ["CCU grade", str(meta.get("ccu_grade", "—"))],
        ["Preset", str(meta.get("preset_label", "Custom"))],
    ]
    tbl = Table(rows, colWidths=[55 * mm, 110 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#CFD8DC")),
        ("TEXTCOLOR", (0, 0), (0, -1), ACCENT_GRAY),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 11),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B0BEC5")),
        ("BOX", (0, 0), (-1, -1), 0.5, ACCENT_GRAY),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl


def _build_kpi_summary_row(results: list[dict], styles) -> Table:
    """4-column KPI banner: best profit, best COCA, best Net COCA, best CRCF"""
    if not results:
        return Spacer(1, 1)

    best_profit = max(results, key=lambda r: _safe_num(r.get("annual_profit_usd")))
    best_coca = min(results, key=lambda r: _safe_num(r.get("COCA"), 1e9))
    best_net = min(results, key=lambda r: _safe_num(r.get("Net_COCA"), 1e9))
    best_crcf = max(results, key=lambda r: _safe_num(r.get("crcf_efficiency_pct")))

    cards = [
        ("Best Annual Profit",
         _fmt_money_usd(_safe_num(best_profit.get("annual_profit_usd"))),
         best_profit.get("name", "—"), ACCENT_GREEN),
        ("Lowest COCA [USD/tCO<sub>2</sub>]",
         f"${_safe_num(best_coca.get('COCA')):,.1f}",
         best_coca.get("name", "—"), ACCENT_BLUE),
        ("Lowest Net COCA [USD/tCO<sub>2</sub>]",
         f"${_safe_num(best_net.get('Net_COCA')):,.1f}",
         best_net.get("name", "—"), ACCENT_ORANGE),
        ("Highest CRCF Eff. [%]",
         f"{_safe_num(best_crcf.get('crcf_efficiency_pct')):,.1f}",
         best_crcf.get("name", "—"), ACCENT_GREEN),
    ]

    cells = []
    row1, row2, row3 = [], [], []
    for label, value, tech, _ in cards:
        row1.append(Paragraph(label, styles["kpi_label"]))
        row2.append(Paragraph(value, styles["kpi_big"]))
        row3.append(Paragraph(f"<i>{tech[:32]}</i>", styles["kpi_label"]))
    cells = [row1, row2, row3]

    col_w = (A4[0] - 30 * mm) / 4
    tbl = Table(cells, colWidths=[col_w] * 4, rowHeights=[10 * mm, 14 * mm, 8 * mm])

    style_cmds = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, 0), (-1, -1), 0, colors.white),
    ]
    # Box around each card
    for i, (_, _, _, accent) in enumerate(cards):
        style_cmds.append(("BOX", (i, 0), (i, -1), 0.5, accent))
        style_cmds.append(("BACKGROUND", (i, 0), (i, 0), accent))
        style_cmds.append(("TEXTCOLOR", (i, 0), (i, 0), colors.white))
    tbl.setStyle(TableStyle(style_cmds))
    return tbl


def _build_results_table(results: list[dict], styles, fx_krw: float) -> Table:
    """Main results table — 1 row per technology."""
    headers = [
        "Technology",
        "TRL",
        "SRD\n[GJ/tCO<sub>2</sub>]",
        "We<sub>elec</sub>\n[GJe/tCO<sub>2</sub>]",
        "COCA\n[USD/tCO<sub>2</sub>]",
        "Net COCA\n[USD/tCO<sub>2</sub>]",
        "Annual Profit\n[USD/yr]",
        "NPV\n[USD]",
        "Payback\n[yr]",
        "CRCF Eff.\n[%]",
    ]
    header_paragraphs = [Paragraph(h, styles["small"]) for h in headers]

    table_data = [header_paragraphs]
    for r in results:
        name = (r.get("name", "—") or "—")[:40]
        # Replace CO₂ with CO<sub>2</sub> if any (technology names are mostly safe)
        name_p = Paragraph(name, styles["small"])
        profit = _safe_num(r.get("annual_profit_usd"))
        npv = _safe_num(r.get("npv"))
        payback = r.get("payback_yr")
        payback_str = f"{_safe_num(payback):.1f}" if payback else "—"

        row = [
            name_p,
            f"{int(_safe_num(r.get('TRL'), 7))}",
            f"{_safe_num(r.get('SRD')):,.2f}",
            f"{_safe_num(r.get('We_elec')):,.2f}",
            f"{_safe_num(r.get('COCA')):,.1f}",
            f"{_safe_num(r.get('Net_COCA')):,.1f}",
            _fmt_money_usd(profit),
            _fmt_money_usd(npv),
            payback_str,
            f"{_safe_num(r.get('crcf_efficiency_pct')):,.1f}",
        ]
        table_data.append(row)

    col_w = [38 * mm, 9 * mm, 16 * mm, 16 * mm, 17 * mm,
              19 * mm, 22 * mm, 18 * mm, 14 * mm, 14 * mm]
    # Total = 183mm, A4 usable ~170mm — adjust if needed; use scaled width
    avail_w = A4[0] - 26 * mm
    scale_factor = avail_w / sum(col_w)
    col_w = [w * scale_factor for w in col_w]

    tbl = Table(table_data, colWidths=col_w, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), HEADER_FG),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B0BEC5")),
        ("BOX", (0, 0), (-1, -1), 0.5, ACCENT_GRAY),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    # Alternate row shading
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
    # Color profit column (index 6)
    for i, r in enumerate(results, start=1):
        profit = _safe_num(r.get("annual_profit_usd"))
        style_cmds.append(("TEXTCOLOR", (6, i), (6, i), _profit_color(profit)))
        style_cmds.append(("FONTNAME", (6, i), (6, i), "Helvetica-Bold"))
    tbl.setStyle(TableStyle(style_cmds))
    return tbl


def _build_lca_table(results: list[dict], styles) -> Table:
    """LCA / Net CO2 breakdown table."""
    headers = [
        "Technology",
        "Stored/Sold\n[tCO<sub>2</sub>/tCO<sub>2</sub>]",
        "LCA Total\n[tCO<sub>2</sub>e/tCO<sub>2</sub>]",
        "Net Removed\n[tCO<sub>2</sub>/tCO<sub>2</sub>]",
        "CRCF Eff.\n[%]",
        "Solvent Loss\n[kg/tCO<sub>2</sub>]",
    ]
    header_paragraphs = [Paragraph(h, styles["small"]) for h in headers]
    table_data = [header_paragraphs]

    for r in results:
        name = (r.get("name", "—") or "—")[:40]
        row = [
            Paragraph(name, styles["small"]),
            f"{_safe_num(r.get('gross_per_t')):,.3f}",
            f"{_safe_num(r.get('lca_e_total')):,.3f}",
            f"{_safe_num(r.get('net_removed_per_t')):,.3f}",
            f"{_safe_num(r.get('crcf_efficiency_pct')):,.1f}",
            f"{_safe_num(r.get('loss_kg_per_tCO2')):,.2f}",
        ]
        table_data.append(row)

    avail_w = A4[0] - 26 * mm
    col_w = [55, 22, 22, 22, 18, 22]
    s = avail_w / sum(col_w)
    col_w = [w * s for w in col_w]

    tbl = Table(table_data, colWidths=col_w, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), HEADER_FG),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B0BEC5")),
        ("BOX", (0, 0), (-1, -1), 0.5, ACCENT_GRAY),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
    tbl.setStyle(TableStyle(style_cmds))
    return tbl


def _maybe_add_chart(story, png_bytes: bytes | None, caption: str, styles,
                      max_width_mm: float = 170, max_height_mm: float = 90):
    """Append a chart image with caption if PNG bytes provided."""
    if not png_bytes:
        return
    try:
        img = Image(io.BytesIO(png_bytes))
        # Scale to fit
        iw, ih = img.imageWidth, img.imageHeight
        target_w = max_width_mm * mm
        target_h = max_height_mm * mm
        ratio = min(target_w / iw, target_h / ih)
        img.drawWidth = iw * ratio
        img.drawHeight = ih * ratio
        story.append(img)
        story.append(Paragraph(caption, styles["small"]))
        story.append(Spacer(1, 4 * mm))
    except Exception as e:
        story.append(Paragraph(f"[Chart unavailable: {e}]", styles["small"]))


# ─────────────────────────────────────────────────────────────
# Main entry
# ─────────────────────────────────────────────────────────────
def build_pdf_report(
    results: list[dict],
    meta: dict,
    fx_krw_per_usd: float = 1380.0,
    chart_pngs: dict[str, bytes] | None = None,
    insights: Iterable[str] | None = None,
    schema_version: str = "1.0",
) -> bytes:
    """
    Build a multi-page PDF report from CCUS benchmark results.

    Args:
        results: list of dicts (rows from app.py's `results` list)
        meta: dict with capture_mt_yr, facility_mode, project_scenario, etc.
        fx_krw_per_usd: exchange rate
        chart_pngs: optional dict like {"profit_bars": <png_bytes>, "coca_bars": ...}
        insights: optional iterable of plain-text insight strings (no HTML)
        schema_version: ccus_metrics.json schema version

    Returns:
        bytes — PDF file content
    """
    chart_pngs = chart_pngs or {}
    styles = _build_styles()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=13 * mm,
        rightMargin=13 * mm,
        topMargin=20 * mm,
        bottomMargin=15 * mm,
        title="CCUS Tech-Economic Benchmark Report",
        author="Song BK (DAC & CCUS specialist)",
        subject="CCUS technology comparison",
    )

    story = []

    # ── Title block ──
    story.append(Paragraph(
        "CO<sub>2</sub> Capture &amp; CCUS — Tech-Economic Benchmark Report",
        styles["title"],
    ))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} &nbsp;·&nbsp; "
        f"Data schema v{schema_version} (data/ccus_metrics.json) &nbsp;·&nbsp; "
        f"Author: Song BK (cafeon90@gmail.com)",
        styles["subtitle"],
    ))

    # ── KPI summary banner ──
    story.append(_build_kpi_summary_row(results, styles))
    story.append(Spacer(1, 6 * mm))

    # ── Scenario meta card ──
    story.append(Paragraph("Scenario configuration", styles["h2"]))
    story.append(_build_meta_card(meta, styles))
    story.append(Spacer(1, 4 * mm))

    # ── Insights (if any) ──
    if insights:
        story.append(Paragraph("Key insights", styles["h2"]))
        for ins in insights:
            # Strip HTML/emojis defensively
            ins_clean = (ins or "").replace("**", "").replace("`", "")
            # Replace some unicode chars that Helvetica lacks
            ins_clean = (ins_clean
                          .replace("CO₂", "CO<sub>2</sub>")
                          .replace("tCO₂", "tCO<sub>2</sub>")
                          .replace("→", "->").replace("⇌", "<->")
                          .replace("•", "-"))
            story.append(Paragraph("- " + ins_clean, styles["body"]))
        story.append(Spacer(1, 4 * mm))

    # ── Main results table ──
    story.append(Paragraph("Results — per-technology summary", styles["h2"]))
    story.append(_build_results_table(results, styles, fx_krw_per_usd))
    story.append(Spacer(1, 5 * mm))

    # ── Charts (page 2+) ──
    if chart_pngs:
        story.append(PageBreak())
        story.append(Paragraph("Charts", styles["h2"]))
        for chart_key, caption in [
            ("profit_bars",
             "Annual profit by technology (positive = profit, negative = loss)."),
            ("coca_bars",
             "COCA — capture cost per tCO<sub>2</sub>. Lower is better."),
            ("net_coca_bars",
             "Net COCA — incentive-adjusted cost per tCO<sub>2</sub>."),
            ("energy_bars",
             "Energy penalty breakdown — SRD (thermal) and We (electric equivalent)."),
        ]:
            _maybe_add_chart(story, chart_pngs.get(chart_key), caption, styles)

    # ── LCA section (page 3+) ──
    story.append(PageBreak())
    story.append(Paragraph("LCA / Net CO<sub>2</sub> breakdown", styles["h2"]))
    story.append(Paragraph(
        "Per-tCO<sub>2</sub> captured, accounting for Scope 1/2/3 emissions of the "
        "capture process itself (heat, electricity, solvent loss). "
        "CRCF efficiency = net removed / captured (CRCF/ICVCM-aligned).",
        styles["body"],
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(_build_lca_table(results, styles))
    story.append(Spacer(1, 6 * mm))

    # ── Methodology note ──
    story.append(Paragraph("Methodology &amp; sources", styles["h2"]))
    story.append(Paragraph(
        "<b>CAPEX scaling</b>: Lang's six-tenths rule (n = 0.65), reference 3.7 Mt/yr "
        "(NETL B12B baseline). <b>Capture rate effect</b>: IEAGHG 2019 (90%->99% adds "
        "+18% SRD). <b>SRD scaling</b>: ±10%/decade (IEAGHG 2013/04). "
        "<b>Equivalent work</b>: We = We<sub>thermal</sub>(Carnot eta x 0.55) + pumps + "
        "compression + chillers + auxiliaries. <b>Financial</b>: NPV/IRR with CRF, "
        "lifetime 25 yr default, discount 8%. "
        "<b>Data source</b>: NETL Rev4a/2022, IEAGHG, IRS 45Q, KIER, "
        "MHI/Shell/Aker vendor data. Full audit trail in app Tab IX (References).",
        styles["body"],
    ))
    story.append(Spacer(1, 5 * mm))

    # ── Disclaimer ──
    story.append(Paragraph(
        "<b>Disclaimer:</b> Values shown are representative figures derived from public "
        "reports. Real projects require EPC quotes and pilot data calibration. "
        "Tier-C technologies (pilot stage) may vary +/-25% at commercial scale.",
        styles["small"],
    ))

    # ── Build ──
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes


# ─────────────────────────────────────────────────────────────
# Smoke test
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    fake_results = [
        {
            "key": "MEA_baseline", "name": "MEA 30 wt% (reference)",
            "category": "Amine (ref)", "TRL": 9,
            "SRD": 3.60, "We_elec": 0.45, "COCA": 75.0, "Net_COCA": -10.0,
            "annual_profit_usd": -5_500_000, "npv": -45_000_000,
            "payback_yr": None, "crcf_efficiency_pct": 62.5,
            "gross_per_t": 0.90, "lca_e_total": 0.337,
            "net_removed_per_t": 0.563, "loss_kg_per_tCO2": 1.5,
        },
        {
            "key": "Cansolv_DC103", "name": "Cansolv DC-103",
            "category": "Advanced amine", "TRL": 9,
            "SRD": 2.50, "We_elec": 0.42, "COCA": 60.0, "Net_COCA": -25.0,
            "annual_profit_usd": 12_500_000, "npv": 80_000_000,
            "payback_yr": 6.8, "crcf_efficiency_pct": 71.2,
            "gross_per_t": 0.90, "lca_e_total": 0.259,
            "net_removed_per_t": 0.641, "loss_kg_per_tCO2": 0.4,
        },
        {
            "key": "CaL", "name": "Calcium Looping (CaL)",
            "category": "Non-amine", "TRL": 7,
            "SRD": 3.20, "We_elec": 0.55, "COCA": 68.0, "Net_COCA": -18.0,
            "annual_profit_usd": 4_200_000, "npv": 25_000_000,
            "payback_yr": 9.5, "crcf_efficiency_pct": 65.0,
            "gross_per_t": 0.90, "lca_e_total": 0.315,
            "net_removed_per_t": 0.585, "loss_kg_per_tCO2": 5.0,
        },
    ]
    fake_meta = {
        "facility_mode": "CCS",
        "project_scenario": "retrofit_industrial",
        "capture_mt_yr": 1.4,
        "cm_select": "K-ETS",
        "sub_select": "K-CCUS-est",
        "fx": 1380,
        "ccu_grade": "—",
        "preset_label": "KR cement retrofit (smoke test)",
    }
    fake_insights = [
        "Cansolv DC-103 leads with $12.5M/yr profit at TRL 9 — most bankable option.",
        "CaL reaches positive Net COCA (-$18/t) but TRL 7 carries +/-25% uncertainty.",
        "MEA baseline operates at loss ($5.5M/yr) without 45Q stack — used as reference only.",
    ]
    pdf_bytes = build_pdf_report(
        fake_results, fake_meta, fx_krw_per_usd=1380,
        insights=fake_insights, schema_version="1.0",
    )
    with open("smoke_test_report.pdf", "wb") as f:
        f.write(pdf_bytes)
    print(f"OK_PDF_BUILT bytes={len(pdf_bytes)} -> smoke_test_report.pdf")
