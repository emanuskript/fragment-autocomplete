#!/usr/bin/env python3
"""Build the notebook-friendly Fragment Autocomplete project study guide."""

from __future__ import annotations

import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "Fragment_Autocomplete_Project_Study_Guide.pdf"

NAVY = colors.HexColor("#15243B")
INK = colors.HexColor("#243047")
TEAL = colors.HexColor("#2A9D8F")
BLUE = colors.HexColor("#4777A8")
PURPLE = colors.HexColor("#6C63A8")
CORAL = colors.HexColor("#E66C55")
AMBER = colors.HexColor("#E9B949")
PARCHMENT = colors.HexColor("#F6F0E2")
CREAM = colors.HexColor("#FFFDF7")
MINT = colors.HexColor("#E6F4EF")
PALE_BLUE = colors.HexColor("#EAF1F8")
PALE_PURPLE = colors.HexColor("#F0EDF9")
PALE_CORAL = colors.HexColor("#FBECE8")
PALE_AMBER = colors.HexColor("#FFF5D7")
MID_GREY = colors.HexColor("#687386")
LIGHT_GREY = colors.HexColor("#E4E8EE")
WHITE = colors.white


def register_fonts() -> tuple[str, str, str]:
    candidates = [
        (
            "/System/Library/Fonts/Supplemental/Avenir Next.ttc",
            "/System/Library/Fonts/Supplemental/Georgia.ttf",
        ),
        (
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        ),
    ]
    for sans_path, serif_path in candidates:
        if os.path.exists(sans_path) and os.path.exists(serif_path):
            try:
                pdfmetrics.registerFont(TTFont("StudySans", sans_path, subfontIndex=0))
                pdfmetrics.registerFont(TTFont("StudySerif", serif_path))
                return "StudySans", "StudySans", "StudySerif"
            except Exception:
                continue
    return "Helvetica", "Helvetica-Bold", "Times-Roman"


SANS, SANS_BOLD, SERIF = register_fonts()


def make_styles():
    base = getSampleStyleSheet()
    return {
        "cover_kicker": ParagraphStyle(
            "CoverKicker", parent=base["Normal"], fontName=SANS_BOLD,
            fontSize=10, leading=13, textColor=colors.HexColor("#BFE6DC"),
            tracking=1.5, alignment=TA_CENTER, spaceAfter=10,
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle", parent=base["Title"], fontName=SANS_BOLD,
            fontSize=31, leading=34, textColor=WHITE, alignment=TA_CENTER,
            spaceAfter=13,
        ),
        "cover_sub": ParagraphStyle(
            "CoverSub", parent=base["Normal"], fontName=SERIF,
            fontSize=15, leading=21, textColor=colors.HexColor("#E7EDF5"),
            alignment=TA_CENTER, spaceAfter=16,
        ),
        "cover_note": ParagraphStyle(
            "CoverNote", parent=base["Normal"], fontName=SANS,
            fontSize=9, leading=13, textColor=colors.HexColor("#C5D1E1"),
            alignment=TA_CENTER,
        ),
        "chapter": ParagraphStyle(
            "Chapter", parent=base["Heading1"], fontName=SANS_BOLD,
            fontSize=23, leading=27, textColor=NAVY, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontName=SANS_BOLD,
            fontSize=15, leading=19, textColor=NAVY, spaceBefore=7, spaceAfter=7,
        ),
        "h3": ParagraphStyle(
            "H3", parent=base["Heading3"], fontName=SANS_BOLD,
            fontSize=11.5, leading=15, textColor=BLUE, spaceBefore=5, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontName=SANS,
            fontSize=9.2, leading=13.3, textColor=INK, spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "Small", parent=base["BodyText"], fontName=SANS,
            fontSize=7.8, leading=10.5, textColor=INK,
        ),
        "tiny": ParagraphStyle(
            "Tiny", parent=base["BodyText"], fontName=SANS,
            fontSize=6.8, leading=8.7, textColor=MID_GREY,
        ),
        "bullet": ParagraphStyle(
            "Bullet", parent=base["BodyText"], fontName=SANS,
            fontSize=8.7, leading=12.2, textColor=INK,
            leftIndent=12, firstLineIndent=-7, bulletIndent=3, spaceAfter=4,
        ),
        "callout": ParagraphStyle(
            "Callout", parent=base["BodyText"], fontName=SERIF,
            fontSize=11.5, leading=16, textColor=NAVY,
        ),
        "label": ParagraphStyle(
            "Label", parent=base["Normal"], fontName=SANS_BOLD,
            fontSize=7.2, leading=9, textColor=WHITE, tracking=0.7,
        ),
        "table_head": ParagraphStyle(
            "TableHead", parent=base["Normal"], fontName=SANS_BOLD,
            fontSize=8, leading=10, textColor=WHITE,
        ),
        "table": ParagraphStyle(
            "Table", parent=base["Normal"], fontName=SANS,
            fontSize=7.6, leading=10.2, textColor=INK,
        ),
        "question": ParagraphStyle(
            "Question", parent=base["BodyText"], fontName=SANS_BOLD,
            fontSize=9.5, leading=13, textColor=PURPLE, spaceAfter=5,
        ),
        "quote": ParagraphStyle(
            "Quote", parent=base["BodyText"], fontName=SERIF,
            fontSize=10.5, leading=15, textColor=NAVY, leftIndent=14,
            rightIndent=14, spaceBefore=6, spaceAfter=8,
        ),
    }


ST = make_styles()


def p(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, ST[style])


def bullet(text: str, color: str = "#243047") -> Paragraph:
    return Paragraph(f'<font color="{color}">-</font> {text}', ST["bullet"])


def chapter(number: str, title: str, subtitle: str) -> list:
    return [
        tag(f"Chapter {number}"),
        Spacer(1, 3),
        p(title, "chapter"),
        p(subtitle, "callout"),
        Spacer(1, 8),
        HRFlowable(width="100%", thickness=1.5, color=TEAL, spaceAfter=10),
    ]


def tag(text: str, color=TEAL):
    table = Table([[p(text.upper(), "label")]], colWidths=[48 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("BOX", (0, 0), (-1, -1), 0, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def card(title: str, body: str, tint=PALE_BLUE, accent=BLUE, width=78 * mm):
    inner = [p(title, "h3"), p(body, "small")]
    table = Table([[inner]], colWidths=[width], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), tint),
        ("BOX", (0, 0), (-1, -1), 0.8, accent),
        ("LINEBEFORE", (0, 0), (0, -1), 4, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def two_cards(left, right, widths=(82 * mm, 82 * mm)):
    table = Table([[left, right]], colWidths=list(widths), hAlign="CENTER")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


class NotebookBox(Flowable):
    def __init__(self, title: str, height: float = 48 * mm, color=PURPLE):
        super().__init__()
        self.title = title
        self.height = height
        self.color = color
        self.width = 0

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return availWidth, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(colors.white)
        c.setStrokeColor(self.color)
        c.setLineWidth(1)
        c.roundRect(0, 0, self.width, self.height, 5, fill=1, stroke=1)
        c.setFillColor(self.color)
        c.roundRect(0, self.height - 18, self.width, 18, 5, fill=1, stroke=0)
        c.rect(0, self.height - 18, self.width, 5, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(SANS_BOLD, 8)
        c.drawString(8, self.height - 12, self.title.upper())
        c.setStrokeColor(colors.HexColor("#D7DCE5"))
        c.setLineWidth(0.5)
        y = self.height - 30
        while y > 8:
            c.line(9, y, self.width - 9, y)
            y -= 10


class EvidenceStack(Flowable):
    def __init__(self):
        super().__init__()
        self.height = 67 * mm
        self.width = 0

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return availWidth, self.height

    def draw(self):
        c = self.canv
        rows = [
            ("4  Future hypothesis", "Candidate reconstructions; multiple options; never historical truth", PURPLE),
            ("3  Synthetic ground truth", "Known artificial mask and hidden complete page; experiment only", AMBER),
            ("2  Model-derived evidence", "Mergen labels, polygons, confidence and masks", BLUE),
            ("1  Observed evidence", "Source pixels, IIIF metadata, shelfmark and repository", TEAL),
        ]
        h = 14 * mm
        gap = 2 * mm
        y = 0
        for title, desc, color in reversed(rows):
            c.setFillColor(colors.Color(color.red, color.green, color.blue, alpha=0.13))
            c.setStrokeColor(color)
            c.roundRect(0, y, self.width, h, 5, fill=1, stroke=1)
            c.setFillColor(color)
            c.setFont(SANS_BOLD, 9)
            c.drawString(9, y + h - 12, title)
            c.setFillColor(INK)
            c.setFont(SANS, 7.5)
            c.drawString(9, y + 7, desc)
            y += h + gap


class PipelineMap(Flowable):
    def __init__(self):
        super().__init__()
        self.height = 126 * mm
        self.width = 0

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return availWidth, self.height

    def draw_box(self, c, x, y, w, h, title, sub, color, status):
        c.setFillColor(colors.white)
        c.setStrokeColor(color)
        c.setLineWidth(1.2)
        c.roundRect(x, y, w, h, 5, fill=1, stroke=1)
        c.setFillColor(color)
        c.roundRect(x, y + h - 14, w, 14, 5, fill=1, stroke=0)
        c.rect(x, y + h - 14, w, 4, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(SANS_BOLD, 7.4)
        c.drawString(x + 6, y + h - 10, title)
        c.setFillColor(INK)
        c.setFont(SANS, 6.7)
        lines = sub.split("|")
        for i, line in enumerate(lines[:3]):
            c.drawString(x + 6, y + h - 25 - i * 8, line)
        c.setFillColor(color)
        c.setFont(SANS_BOLD, 6.3)
        c.drawRightString(x + w - 6, y + 6, status)

    def draw_arrow(self, c, x1, y1, x2, y2, color=MID_GREY):
        c.setStrokeColor(color)
        c.setFillColor(color)
        c.setLineWidth(1)
        c.line(x1, y1, x2, y2)
        c.line(x2, y2, x2 - 4, y2 + 3)
        c.line(x2, y2, x2 - 4, y2 - 3)

    def draw(self):
        c = self.canv
        w = (self.width - 12) / 2
        h = 28 * mm
        y1 = self.height - h
        y2 = self.height - 2 * h - 11
        y3 = self.height - 3 * h - 22
        y4 = self.height - 4 * h - 33
        self.draw_box(c, 0, y1, w, h, "1. SOURCES + IIIF", "Manifests and page images|Stable identifiers|Repository metadata", TEAL, "IMPLEMENTED")
        self.draw_box(c, w + 12, y1, w, h, "2. REGISTER + RIGHTS", "PostgreSQL/PostGIS|Checksums and raw metadata|Training permission separate", BLUE, "IMPLEMENTED")
        self.draw_arrow(c, w, y1 + h / 2, w + 12, y1 + h / 2)
        self.draw_box(c, 0, y2, w, h, "3. MERGEN SEGMENTATION", "Detect layout regions|Restore source-sized masks|Record confidence + model", BLUE, "IMPLEMENTED")
        self.draw_box(c, w + 12, y2, w, h, "4. SYNTHETIC DAMAGE", "Create controlled fragments|Keep survival/damage masks|Known hidden complete page", AMBER, "IMPLEMENTED")
        self.draw_arrow(c, w, y2 + h / 2, w + 12, y2 + h / 2)
        self.draw_box(c, 0, y3, w, h, "5. EVALUATE", "Layout survival metrics|Determinism + audit|No semantic recovery claim", TEAL, "PARTIAL")
        self.draw_box(c, w + 12, y3, w, h, "6. RETRIEVE + PROPOSE", "Find analogues or same codex|Generate multiple candidates|Rank with comparators", PURPLE, "NOT BUILT")
        self.draw_arrow(c, w, y3 + h / 2, w + 12, y3 + h / 2)
        self.draw_box(c, 0, y4, w, h, "7. EXPERT REVIEW", "Accept, reject, annotate|Preserve disagreement|No autonomous outreach", CORAL, "NOT BUILT")
        self.draw_box(c, w + 12, y4, w, h, "8. EXPORT + HANDOFF", "Fragmentarium-compatible data|Evidence bundle|Long-term maintenance", PURPLE, "NOT BUILT")
        self.draw_arrow(c, w, y4 + h / 2, w + 12, y4 + h / 2)


class StatusMeter(Flowable):
    def __init__(self, items):
        super().__init__()
        self.items = items
        self.height = len(items) * 12 * mm
        self.width = 0

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return availWidth, self.height

    def draw(self):
        c = self.canv
        for i, (name, ratio, label, color) in enumerate(self.items):
            y = self.height - (i + 1) * 12 * mm + 3
            c.setFillColor(INK)
            c.setFont(SANS_BOLD, 7.5)
            c.drawString(0, y + 10, name)
            c.setFillColor(LIGHT_GREY)
            c.roundRect(0, y, self.width - 58, 6, 3, fill=1, stroke=0)
            c.setFillColor(color)
            c.roundRect(0, y, (self.width - 58) * ratio, 6, 3, fill=1, stroke=0)
            c.setFillColor(color)
            c.setFont(SANS_BOLD, 7)
            c.drawRightString(self.width, y + 1, label)


def status_table(rows):
    data = [[p("AREA", "table_head"), p("STATE", "table_head"), p("WHAT THAT MEANS", "table_head")]]
    for area, state, meaning in rows:
        data.append([p(area, "table"), p(state, "table"), p(meaning, "table")])
    t = Table(data, colWidths=[45 * mm, 28 * mm, 94 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.45, LIGHT_GREY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#F7F9FC")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def draw_cover(canvas, doc):
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    canvas.setFillColor(TEAL)
    canvas.circle(width - 22 * mm, height - 30 * mm, 34 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#213553"))
    canvas.circle(18 * mm, 29 * mm, 44 * mm, fill=1, stroke=0)
    canvas.setStrokeColor(colors.Color(1, 1, 1, alpha=0.16))
    for x in range(18, 200, 18):
        canvas.line(x * mm, 0, x * mm, height)
    for y in range(18, 290, 18):
        canvas.line(0, y * mm, width, y * mm)
    canvas.restoreState()


def draw_page(canvas, doc):
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(CREAM)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    canvas.setStrokeColor(LIGHT_GREY)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, height - 16 * mm, width - 18 * mm, height - 16 * mm)
    canvas.setFillColor(MID_GREY)
    canvas.setFont(SANS, 7)
    canvas.drawString(18 * mm, height - 12 * mm, "FRAGMENT AUTOCOMPLETE - PROJECT STUDY GUIDE")
    canvas.drawRightString(width - 18 * mm, height - 12 * mm, "CURRENT TO 26 OCTOBER 2026")
    canvas.setStrokeColor(LIGHT_GREY)
    canvas.line(18 * mm, 14 * mm, width - 18 * mm, 14 * mm)
    canvas.setFillColor(MID_GREY)
    canvas.setFont(SANS, 7)
    canvas.drawString(18 * mm, 9 * mm, "Evidence first. Candidates, not recovered truth.")
    canvas.drawRightString(width - 18 * mm, 9 * mm, str(doc.page))
    canvas.restoreState()


def build_story():
    story = []

    # Cover
    story += [
        Spacer(1, 50 * mm),
        p("A NOTEBOOK COURSE FOR MO", "cover_kicker"),
        p("Fragment Autocomplete", "cover_title"),
        p("The whole project, from Fragmentarium and IIIF<br/>to layout masks, synthetic damage, future reconstruction,<br/>and the decisions you need to make next.", "cover_sub"),
        Spacer(1, 12 * mm),
        Table([[p("READ", "label"), p("DRAW", "label"), p("DECIDE", "label")]],
              colWidths=[38 * mm] * 3, hAlign="CENTER",
              style=TableStyle([
                  ("BACKGROUND", (0, 0), (0, 0), TEAL),
                  ("BACKGROUND", (1, 0), (1, 0), BLUE),
                  ("BACKGROUND", (2, 0), (2, 0), CORAL),
                  ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                  ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                  ("BOX", (0, 0), (-1, -1), 0.5, WHITE),
                  ("LEFTPADDING", (0, 0), (-1, -1), 8),
                  ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                  ("TOPPADDING", (0, 0), (-1, -1), 7),
                  ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
              ])),
        Spacer(1, 35 * mm),
        p("Bring a notebook. Every chapter ends with something worth writing down.", "cover_note"),
        Spacer(1, 4 * mm),
        p("Prepared from the repository's current code, audits, roadmap and evidence records.", "cover_note"),
        PageBreak(),
    ]

    # How to use
    story += chapter("0", "How to study this guide", "You do not need to understand the code first. Build a mental map, then attach the technical details to it.")
    story += [
        two_cards(
            card("Fast route - 45 minutes", "Read pages 3-7, 12-17 and the final cheat sheet. Answer only the purple notebook prompts.", MINT, TEAL),
            card("Deep route - 2 to 3 hours", "Read every page. Redraw the pipeline from memory. Use the glossary, quiz and decision worksheet.", PALE_PURPLE, PURPLE),
        ),
        Spacer(1, 8),
        p("Use three notebook columns", "h2"),
        status_table([
            ("FACT", "Observed", "What the repository or source data actually contains."),
            ("INTERPRETATION", "Model or analyst", "What a model, metric or human infers from the evidence."),
            ("DECISION", "Governance", "What the project is authorised to do next."),
        ]),
        Spacer(1, 10),
        p("The one sentence to memorise", "h2"),
        card("Project thesis", "Fragment Autocomplete tests whether layout and morphology can support transparent scholarly candidate reconstruction of damaged manuscript pages, while keeping evidence, model output and inference separate.", PALE_AMBER, AMBER, 168 * mm),
        Spacer(1, 10),
        NotebookBox("Write your current understanding of the project in three sentences", 54 * mm),
        PageBreak(),
    ]

    # Who is who
    story += chapter("1", "Who is who?", "Most confusion comes from five names that sound related but do different jobs.")
    who = [
        ("Fragmentarium", "The international platform and catalogue for medieval manuscript fragments. It publishes images, descriptions and IIIF links. It is a potential long-term home or integration partner - not this repository."),
        ("Fragment Autocomplete", "This research project and repository. It currently studies layout, provenance, controlled damage and evaluation. It does not yet reconstruct missing historical content."),
        ("eManuSkript / Mergen", "The central visual layout-analysis backbone. Mergen is the eManuSkript component used here to detect regions such as main script, glosses, initials and music."),
        ("IIIF", "A standard way for libraries to publish image manifests, page identifiers and image services. It lets the project fetch and cite the right page reproducibly."),
        ("CoMMA", "A large machine-read manuscript text corpus. It may support text retrieval and metadata links, but it is not this project's visual training dataset or ground truth."),
        ("Andrew / Google efforts", "External candidate collaborations: one for identifying texts; one reportedly for linking fragments from the same manuscript. They are not presently integrated into this codebase."),
    ]
    for i in range(0, len(who), 2):
        story.append(two_cards(
            card(who[i][0], who[i][1], [MINT, PALE_BLUE, PALE_AMBER][(i // 2) % 3], [TEAL, BLUE, AMBER][(i // 2) % 3]),
            card(who[i + 1][0], who[i + 1][1], [PALE_PURPLE, PALE_CORAL, PALE_BLUE][(i // 2) % 3], [PURPLE, CORAL, BLUE][(i // 2) % 3]),
        ))
        story.append(Spacer(1, 6))
    story += [
        NotebookBox("Draw six circles and connect only the relationships you can explain", 48 * mm),
        PageBreak(),
    ]

    # Problem and safety
    story += chapter("2", "The problem - and the safety contract", "A damaged page invites imagination. The project must make that imagination inspectable rather than disguising it as recovery.")
    story += [
        p("The research problem", "h2"),
        bullet("Fragments preserve incomplete geometry, partial writing areas, cropped decorations, missing neighbours and uncertain original position."),
        bullet("A useful system may propose compatible page structures or related witnesses, but the surviving pixels do not uniquely determine the missing content."),
        bullet("The scholarly task is therefore candidate generation and comparison, not automatic historical restoration."),
        Spacer(1, 7),
        p("The four evidence layers", "h2"),
        EvidenceStack(),
        Spacer(1, 9),
        two_cards(
            card("Allowed language", "candidate, comparator, plausible, model-derived, source-assisted, unresolved, confidence, evidence, inference", MINT, TEAL),
            card("Language to avoid", "recovered, restored original, true missing text, definitive reconstruction - unless specific external scholarly evidence supports the claim", PALE_CORAL, CORAL),
        ),
        Spacer(1, 8),
        NotebookBox("Explain why a beautiful completion can still be bad scholarship", 42 * mm, CORAL),
        PageBreak(),
    ]

    # Full pipeline
    story += chapter("3", "The whole pipeline on one page", "Read top to bottom. The project currently reaches Stage 5; Stages 6-8 are future work.")
    story += [
        PipelineMap(),
        Spacer(1, 8),
        card("Memory trick", "SOURCE -> REGISTER -> SEGMENT -> DAMAGE -> MEASURE -> RETRIEVE -> REVIEW -> EXPORT", PALE_PURPLE, PURPLE, 168 * mm),
        Spacer(1, 8),
        NotebookBox("Close the guide and redraw the eight stages from memory", 40 * mm),
        PageBreak(),
    ]

    # Stage 1
    story += chapter("4", "Stage 1 - Images arrive through IIIF", "Before any AI runs, the project must know exactly which manuscript, page, image and institution it is looking at.")
    story += [
        p("What IIIF contributes", "h2"),
        status_table([
            ("Manifest", "Metadata packet", "Names the manuscript object and lists canvases/pages."),
            ("Canvas", "Page identity", "A stable surface that represents one page or view."),
            ("Image service", "Pixels", "Provides an image at requested size or region."),
            ("Source URL", "Provenance", "Lets another researcher trace the asset back to its publisher."),
        ]),
        Spacer(1, 9),
        p("What the repository already does", "h2"),
        bullet("Normalises common IIIF Presentation API v2 and v3 structures."),
        bullet("Registers repository, manuscript, manifest, canvas and image-asset identifiers."),
        bullet("Downloads selected pages resumably, records SHA-256 checksums and keeps source files outside Git."),
        bullet("Preserves raw upstream metadata alongside normalised fields."),
        Spacer(1, 8),
        card("Why this matters", "Without stable source identity, a later mask or candidate cannot be checked. Provenance is part of the scientific result, not administrative decoration.", PALE_AMBER, AMBER, 168 * mm),
        Spacer(1, 9),
        NotebookBox("In one line each: manifest, canvas, image service, checksum", 55 * mm),
        PageBreak(),
    ]

    # Stage 2
    story += chapter("5", "Stage 2 - Registration, storage and rights", "The system stores small, queryable facts separately from large images and model artifacts.")
    story += [
        two_cards(
            card("PostgreSQL/PostGIS", "Stable IDs, normalised metadata, geometry, JSON provenance, segmentation runs, layout regions and artificial-fragment task records.", PALE_BLUE, BLUE),
            card("Filesystem", "Raw IIIF images, masks, overlays, generated fragments and model checkpoints. Large binaries are ignored by Git.", PALE_AMBER, AMBER),
        ),
        Spacer(1, 9),
        two_cards(
            card("Git", "Code, tests, migrations, compact YAML/JSON specs, checksums, decisions, validation results and documentation.", MINT, TEAL),
            card("External model storage", "Mergen checkpoints remain outside Git. Their source, expected filenames and verified checksums are registered.", PALE_PURPLE, PURPLE),
        ),
        Spacer(1, 10),
        p("The rights rule that blocks training today", "h2"),
        card("Source access is not training permission", "All 85 current corpus pages remain rights_review_status: pending_review and training_allowed: false. An open image service, a source licence and a successful download do not automatically authorise model training.", PALE_CORAL, CORAL, 168 * mm),
        Spacer(1, 10),
        p("Four different decisions", "h2"),
        status_table([
            ("Acquire", "Can we fetch it?", "Technical access and source terms."),
            ("Analyse", "Can we run inference?", "Research use and local processing."),
            ("Train", "Can it update weights?", "Requires explicit reviewed authorization."),
            ("Publish", "Can we show outputs?", "May differ from acquisition and training rights."),
        ]),
        Spacer(1, 8),
        NotebookBox("What approval would you require before training begins?", 40 * mm, CORAL),
        PageBreak(),
    ]

    # Stage 3
    story += chapter("6", "Stage 3 - Mergen reads page layout", "Segmentation asks where visual regions are. It does not identify the text and it does not reconstruct missing content.")
    story += [
        p("Input", "h2"),
        bullet("A registered complete page or fragment image with source dimensions and provenance."),
        p("Model operation", "h2"),
        bullet("The Mergen/Ultralytics checkpoint predicts layout classes, bounding geometry, confidence and instance masks."),
        p("Output", "h2"),
        bullet("Source-coordinate binary masks plus a fully recorded model version and inference configuration."),
        Spacer(1, 8),
        status_table([
            ("Main script black", "Dominant class", "3,889 of 4,230 detected regions in the current corpus."),
            ("Music / gloss / initials", "Present", "Useful specialist structures, but unevenly distributed."),
            ("Border / illustration / table", "Rare", "Only one, six and one regions respectively in the full corpus."),
            ("Zero-region pages", "Quality flag", "Four validation pages have no detections and require review."),
        ]),
        Spacer(1, 9),
        two_cards(
            card("What a mask proves", "The model detected pixels as a particular layout class at a recorded confidence.", MINT, TEAL),
            card("What it does not prove", "That the label is correct, that nothing else exists, or that missing text can be inferred.", PALE_CORAL, CORAL),
        ),
        Spacer(1, 9),
        NotebookBox("Give one possible Mergen false positive and one false negative", 45 * mm),
        PageBreak(),
    ]

    # Stage 4
    story += chapter("7", "Stage 4 - We damage complete pages on purpose", "Synthetic fragments create known experimental ground truth: we know exactly what was hidden because we started with the complete page.")
    story += [
        p("Why synthetic damage?", "h2"),
        bullet("Real fragments do not come with their missing original page, so reconstruction accuracy cannot be measured directly."),
        bullet("Controlled masks let us measure which model-detected layout regions survive a known loss pattern."),
        bullet("Seeds, transforms and mask geometry make the experiment reproducible."),
        Spacer(1, 8),
        p("Experiment versions", "h2"),
        status_table([
            ("v0.1.1", "Pilot", "23 original tasks: rectangular/irregular masks and sanity checks."),
            ("v0.2", "Validation", "44 tasks on 11 then-available validation pages; 604 region measurements."),
            ("v0.3", "Current milestone", "156 tasks on all 13 validation pages; six structured damage families; 2,424 observations."),
        ]),
        Spacer(1, 10),
        card("Do not confuse experiment truth with history", "The hidden source page is ground truth only for the artificial task. The mask does not claim that a historical fragment was damaged in the same way.", PALE_CORAL, CORAL, 168 * mm),
        Spacer(1, 9),
        NotebookBox("Sketch a complete page, a damage mask, the visible fragment and the hidden source", 53 * mm, AMBER),
        PageBreak(),
    ]

    # Stage 5 evaluation
    story += chapter("8", "Stage 5 - Evaluation asks: what survived?", "The current metrics test reproducibility and layout survival, not whether a missing sentence has been recovered.")
    story += [
        p("Current measurements", "h2"),
        bullet("For every model-derived region, measure how much of its full source mask remains visible after synthetic damage."),
        bullet("Group by damage family, severity, page, manuscript and layout class."),
        bullet("Audit topology, exact severity, source availability, splits, rights, checksums and database idempotency."),
        Spacer(1, 8),
        two_cards(
            card("Strong evidence", "Full recomputation found 795 byte-identical artifacts with unchanged mtimes; 4,873 frozen files and historical task records passed invariant checks.", MINT, TEAL),
            card("Important limit", "Region survival is not semantic recoverability, historical probability or proof that a reconstruction is correct.", PALE_CORAL, CORAL),
        ),
        Spacer(1, 10),
        p("Still missing from evaluation", "h2"),
        status_table([
            ("Retrieval quality", "Not built", "Can the system find the right analogue or same-manuscript page?"),
            ("Candidate ranking", "Not built", "Are useful hypotheses ranked above misleading ones?"),
            ("Placement quality", "Not built", "Does proposed geometry align with surviving evidence?"),
            ("Expert rubric", "Incomplete", "Can specialists record acceptance, rejection and reasons consistently?"),
        ]),
        Spacer(1, 9),
        NotebookBox("Invent one metric that would reward honest uncertainty", 43 * mm, PURPLE),
        PageBreak(),
    ]

    # Current stage dashboard
    story += chapter("9", "Where development stands today", "The foundation and controlled experiment are real. Reconstruction is still a future milestone.")
    story += [
        StatusMeter([
            ("Source ingestion + provenance", 1.00, "IMPLEMENTED", TEAL),
            ("Database + rights fields", 1.00, "IMPLEMENTED", TEAL),
            ("Mergen segmentation + masks", 1.00, "IMPLEMENTED", TEAL),
            ("Synthetic damage experiments", 1.00, "IMPLEMENTED", TEAL),
            ("Evaluation framework", 0.58, "PARTIAL", AMBER),
            ("Local inspection UI", 0.42, "BASIC", AMBER),
            ("Retrieval / same-manuscript search", 0.06, "NOT BUILT", CORAL),
            ("Candidate reconstruction", 0.04, "NOT BUILT", CORAL),
            ("Expert review workflow", 0.03, "NOT BUILT", CORAL),
            ("Fragmentarium export / deployment", 0.03, "NOT BUILT", CORAL),
        ]),
        Spacer(1, 8),
        card("Plain English", "The project has built a careful laboratory bench. It can collect pages, segment them, damage complete pages under controlled conditions and measure what layout survives. It has not yet built the machine that proposes missing content.", PALE_BLUE, BLUE, 168 * mm),
        Spacer(1, 9),
        NotebookBox("If someone asks 'does it reconstruct manuscripts yet?', write your answer", 44 * mm),
        PageBreak(),
    ]

    # Numbers
    story += chapter("10", "Numbers worth remembering", "These numbers describe the current research corpus and experiments. They are not performance scores.")
    data = [
        [p("85", "chapter"), p("19", "chapter"), p("4,230", "chapter")],
        [p("corpus pages", "small"), p("page-bearing manuscripts", "small"), p("model region masks", "small")],
        [p("59 / 13 / 13", "h2"), p("156", "h2"), p("2,424", "h2")],
        [p("train / validation / test pages", "small"), p("v0.3 synthetic tasks", "small"), p("v0.3 region observations", "small")],
        [p("91.94%", "h2"), p("1", "h2"), p("0", "h2")],
        [p("regions labelled Main script black", "small"), p("image provider: e-codices", "small"), p("pages authorised for training", "small")],
    ]
    t = Table(data, colWidths=[56 * mm] * 3)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WHITE),
        ("GRID", (0, 0), (-1, -1), 0.6, LIGHT_GREY),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("BACKGROUND", (0, 0), (-1, 1), MINT),
        ("BACKGROUND", (0, 2), (-1, 3), PALE_BLUE),
        ("BACKGROUND", (0, 4), (-1, 5), PALE_AMBER),
    ]))
    story += [
        t,
        Spacer(1, 10),
        p("What the numbers reveal", "h2"),
        bullet("The split is manuscript-isolated, which reduces leakage between related pages."),
        bullet("The corpus is small, highly concentrated in one provider and dominated by one layout class."),
        bullet("Validation contains no Border, Illustrations, Running header or Table detections."),
        bullet("Four validation pages have zero detected regions; these may be segmentation failures and need human review."),
        bullet("The next corpus batch should target measured gaps, not simply add more similar pages."),
        Spacer(1, 8),
        NotebookBox("Which number worries you most, and why?", 47 * mm, CORAL),
        PageBreak(),
    ]

    # Not built
    story += chapter("11", "What is explicitly not built", "Schema tables and architecture diagrams are plans, not proof of a working subsystem.")
    story += [
        status_table([
            ("Historical reconstruction", "Absent", "No missing manuscript content is generated or claimed as recovered."),
            ("Retrieval embeddings", "Absent", "No similarity index, same-manuscript matcher or analogue ranking."),
            ("Model training", "Absent", "No fine-tuning pipeline, and current rights do not authorise training."),
            ("Production backend", "Absent", "No API service, job queue, authentication or hosted deployment."),
            ("Scholarly frontend", "Absent", "Only a local read-only segmentation viewer exists."),
            ("Expert accept/reject", "Absent", "No workflow for adjudicating candidates and recording reasons."),
            ("Exports", "Absent", "No IIIF annotation, PAGE XML, TEI or Fragmentarium proposal bundle."),
            ("CoMMA / MSI integration", "Absent", "Only concepts and future-facing schema groundwork."),
        ]),
        Spacer(1, 10),
        card("Useful discipline", "Whenever you see a table named reconstruction_candidate or retrieval_embedding, ask: is there runnable code that creates and evaluates it? Today, the answer is no.", PALE_PURPLE, PURPLE, 168 * mm),
        Spacer(1, 10),
        NotebookBox("Choose one 'not built' item and describe its minimum viable version", 51 * mm),
        PageBreak(),
    ]

    # Decisions
    story += chapter("12", "The decisions in front of you", "The next move is not a single coding task. It is a sequence of governance and research choices.")
    decisions = [
        ("1", "Durable storage", "Where will source images, masks and artifacts live so iCloud placeholders cannot silently interrupt reproducibility?", CORAL),
        ("2", "Human quality review", "Who will inspect the four flagged validation pages and the additional zero-detection page?", AMBER),
        ("3", "Rights review", "Which sources may be analysed, trained on, demonstrated and published? Record each decision separately.", CORAL),
        ("4", "Batch 02 design", "Which new complete pages fill missing classes, providers, scripts and layout structures without touching the test set?", TEAL),
        ("5", "Evaluation rubric", "How will Anna, Jeremy, Bill or other specialists judge a future candidate and record uncertainty?", BLUE),
        ("6", "Collaboration boundary", "What can Andrew or Google contribute without taking control of data, claims, communication or maintenance?", PURPLE),
        ("7", "Next technical milestone", "After the gates above: targeted corpus expansion, retrieval pilot, or reconstruction baseline? Do not start all three.", NAVY),
    ]
    for num, title, body, color in decisions:
        row = Table([[p(num, "h2"), [p(title, "h3"), p(body, "small")]]], colWidths=[12 * mm, 153 * mm])
        row.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), color),
            ("TEXTCOLOR", (0, 0), (0, 0), WHITE),
            ("BACKGROUND", (1, 0), (1, 0), WHITE),
            ("BOX", (0, 0), (-1, -1), 0.6, LIGHT_GREY),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story += [row, Spacer(1, 5)]
    story += [
        NotebookBox("Rank the seven decisions: now / next / later", 42 * mm, PURPLE),
        PageBreak(),
    ]

    # Decision gate
    story += chapter("13", "Recommended decision sequence", "This sequence protects the research while still creating momentum.")
    story += [
        status_table([
            ("GATE A", "Protect the evidence", "Durable storage; verify checksums; preserve the frozen baseline."),
            ("GATE B", "Review quality", "Specialists inspect flagged pages and synthetic damage assumptions."),
            ("GATE C", "Authorise rights", "Approve a documented training subset or keep training blocked."),
            ("GATE D", "Design Batch 02", "Add pages that address measured class/provider/script gaps."),
            ("GATE E", "Choose one pilot", "Either retrieval/same-manuscript matching or a bounded layout candidate baseline."),
            ("GATE F", "Build review first", "Candidate comparison, evidence display and accept/reject reasons."),
            ("GATE G", "Integrate/export", "Only after evidence, evaluation and maintenance responsibilities are clear."),
        ]),
        Spacer(1, 12),
        two_cards(
            card("My recommendation now", "Complete Gates A-C while designing Batch 02. In parallel, specify a small retrieval collaboration pilot without integrating it into production.", MINT, TEAL),
            card("What not to do", "Do not begin model training, reconstruction generation and external production integration simultaneously. That would erase the ability to learn which part works.", PALE_CORAL, CORAL),
        ),
        Spacer(1, 12),
        NotebookBox("Write the exact evidence that would let you pass each gate", 66 * mm, TEAL),
        PageBreak(),
    ]

    # External email
    story += chapter("14", "Where Anna's email fits", "The external teams could accelerate future stages, but they should enter through the project's evidence and review boundaries.")
    story += [
        two_cards(
            card("Andrew Aymeloglu", "Public agent workflow for identifying texts in Fragmentarium images. Strong provenance discipline; useful retrieval and reporting tools. Public repository currently has no declared licence and the flagship reports remain model-produced pending human review.", PALE_BLUE, BLUE),
            card("Google group", "Reportedly working on same-manuscript matching and model distillation. Potentially close to the future retrieval stage, but names, code, data rights, benchmarks, licence and deployment terms are not yet available.", PALE_PURPLE, PURPLE),
        ),
        Spacer(1, 10),
        p("Safe collaboration shape", "h2"),
        bullet("Frozen pilot dataset with known positives, hard negatives and unresolved cases."),
        bullet("University-controlled data, repository and evaluation results."),
        bullet("Exact licence for code, prompts, weights and derived outputs."),
        bullet("No autonomous emails, catalogue updates or public claims."),
        bullet("Human review queue with evidence and multiple candidates."),
        bullet("Non-exclusive exit: the project can continue without the partner."),
        Spacer(1, 9),
        card("Key insight", "Andrew's work may help identify what text a fragment contains. Google's work may help identify which fragments belong together. Neither replaces Mergen's layout analysis or the project's responsibility for provenance and scholarly review.", PALE_AMBER, AMBER, 168 * mm),
        Spacer(1, 10),
        NotebookBox("Write five questions you want Bill to answer before any partnership", 58 * mm, PURPLE),
        PageBreak(),
    ]

    # Meeting questions
    story += chapter("15", "Meeting notebook", "Use this page with Anna, Jeremy and Bill. The goal is to turn enthusiasm into testable commitments.")
    story += [
        p("Questions for Bill", "h2"),
        bullet("Which concrete Fragmentarium problem matters most: text identification, same-manuscript linkage, candidate reconstruction, or catalogue workflow?"),
        bullet("What evidence threshold is required before a candidate reaches a librarian?"),
        bullet("Who can provide expert validation and how much review time is realistic?"),
        bullet("What output could Fragmentarium maintain in five years?"),
        p("Questions for Andrew", "h2"),
        bullet("Will the repository receive an explicit licence? Which model versions, costs and data-retention terms does the workflow depend on?"),
        bullet("Can the method be evaluated blindly on a university-defined set and export structured evidence?"),
        p("Questions for Google", "h2"),
        bullet("Who is the team, what is the exact model and licence, and can the distilled weights run independently?"),
        bullet("How were positive and negative pairs defined? What are precision, recall, calibration and failure modes?"),
        bullet("What technical control prevents unreviewed outreach or catalogue modification?"),
        Spacer(1, 10),
        NotebookBox("Meeting notes and names", 73 * mm, BLUE),
        PageBreak(),
    ]

    # 30 day study/action plan
    story += chapter("16", "A calm 30-day plan", "The aim is not to understand everything at once. It is to establish command of the project and unlock one good decision.")
    story += [
        status_table([
            ("Week 1", "Learn the map", "Read this guide; redraw the pipeline; open README, ARCHITECTURE, ROADMAP_STATUS and NEXT_ACTIONS."),
            ("Week 2", "See the evidence", "Run the local viewer; inspect a good segmentation, a zero-detection page and one v0.3 artificial task."),
            ("Week 3", "Meet the humans", "Discuss rights, flagged pages, damage realism, Fragmentarium needs and collaboration terms."),
            ("Week 4", "Make one decision", "Approve the design brief for Batch 02 and a separate small retrieval collaboration evaluation."),
        ]),
        Spacer(1, 12),
        p("The three documents to keep open", "h2"),
        two_cards(
            card("ROADMAP_STATUS.md", "What milestones exist, their evidence and the next action per area.", MINT, TEAL),
            card("NEXT_ACTIONS.md", "The current recommended move, acceptance criteria and explicit blockers.", PALE_AMBER, AMBER),
        ),
        Spacer(1, 6),
        card("docs/ARCHITECTURE.md", "The truthful current component map. Use it instead of treating the May 2026 historical architecture draft as implemented software.", PALE_BLUE, BLUE, 168 * mm),
        Spacer(1, 12),
        NotebookBox("My one decision at the end of 30 days will be...", 57 * mm, TEAL),
        PageBreak(),
    ]

    # Glossary
    story += chapter("17", "Pocket glossary", "Say the term aloud, then explain it without using the term itself.")
    glossary = [
        ("Artificial fragment", "A complete page hidden by a known synthetic mask for controlled evaluation."),
        ("Candidate", "A proposed scholarly hypothesis that remains open to comparison and rejection."),
        ("Canvas", "A stable IIIF page or surface identity."),
        ("Checksum", "A fingerprint used to verify that file bytes have not changed."),
        ("Comparator", "Evidence used to assess one candidate against alternatives."),
        ("Ground truth", "Known answer for a bounded experiment; here, not historical truth."),
        ("Idempotent", "Running the same registration again produces no duplicates or timestamp churn."),
        ("Inference", "A conclusion proposed from evidence, not the evidence itself."),
        ("Layout region", "A model-detected area such as main script, gloss, initial or music."),
        ("Mask", "A pixel-level map marking a region, visible area or simulated damage."),
        ("Provenance", "The trace from an artifact back to source, model, settings and decisions."),
        ("Retrieval", "Finding analogous pages, passages or possible same-manuscript items."),
        ("Segmentation", "Dividing a page image into meaningful visual regions."),
        ("Split", "Train, validation or test assignment, isolated here by manuscript."),
        ("Training authorization", "A reviewed permission state, separate from image access or publication."),
        ("Uncertainty", "A recorded limit on what the evidence supports."),
    ]
    rows = [[p("TERM", "table_head"), p("PLAIN MEANING", "table_head")]] + [[p(a, "table"), p(b, "table")] for a, b in glossary]
    gt = Table(rows, colWidths=[42 * mm, 125 * mm], repeatRows=1)
    gt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.4, LIGHT_GREY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#F8F9FB")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [gt, PageBreak()]

    # Quiz
    story += chapter("18", "Project quiz", "Answer without looking back. The goal is a usable mental model, not perfect wording.")
    questions = [
        "1. What does Fragmentarium do, and what does this repository do?",
        "2. Why is Mergen central to the current project?",
        "3. Why is CoMMA not a visual training dataset?",
        "4. Name the four evidence layers in order.",
        "5. What does a source-coordinate mask preserve?",
        "6. Why generate artificial fragments from complete pages?",
        "7. What does layout survival fail to measure?",
        "8. Which pipeline stages are not built?",
        "9. Why is training blocked even though 85 pages are available?",
        "10. What is the recommended next milestone?",
        "11. How could Andrew's work complement this project?",
        "12. What control would have prevented the Google email incident?",
    ]
    for q in questions:
        story += [p(q, "question"), Spacer(1, 10)]
    story += [NotebookBox("Score yourself: confident / review / ask a human", 45 * mm, PURPLE), PageBreak()]

    # Answer key
    story += chapter("19", "Quiz answer key", "Your wording may differ. Check whether your answer preserves the same boundary.")
    answers = [
        ("1", "Fragmentarium is the international fragment catalogue/platform. Fragment Autocomplete is the research codebase testing layout-first, uncertainty-aware methods."),
        ("2", "Mergen supplies the current visual layout evidence: classes, confidence, geometry and source-coordinate masks."),
        ("3", "CoMMA contains machine-read manuscript text and metadata. It may support retrieval, but it is not the image corpus used to learn visual page structure."),
        ("4", "Observed source evidence; model-derived evidence; synthetic experimental ground truth; future candidate hypotheses."),
        ("5", "It maps the model's region prediction back to the original page pixels so survival can be measured precisely."),
        ("6", "A real fragment lacks a known complete original; synthetic damage provides a controlled hidden source and exact mask."),
        ("7", "It does not measure semantic recovery, historical likelihood or correctness of missing content."),
        ("8", "Retrieval, candidate generation/ranking, expert review, scholarly export, production backend/frontend and deployment."),
        ("9", "All current pages remain pending rights review and training_allowed is false."),
        ("10", "Protect storage, obtain human quality and rights review, then design gap-targeted immutable Corpus Expansion Batch 02."),
        ("11", "As a text-identification/retrieval and provenance component feeding candidates into a university-controlled review process."),
        ("12", "No external communication capability before explicit human approval; outputs stay in a review queue."),
    ]
    for n, ans in answers:
        row = Table([[p(n, "h3"), p(ans, "small")]], colWidths=[12 * mm, 153 * mm])
        row.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), TEAL),
            ("BACKGROUND", (1, 0), (1, 0), WHITE),
            ("BOX", (0, 0), (-1, -1), 0.5, LIGHT_GREY),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story += [row, Spacer(1, 4)]
    story += [PageBreak()]

    # Cheat sheet
    story += chapter("20", "One-page cheat sheet", "If everything else blurs, return here.")
    story += [
        p("THE PROJECT", "h2"),
        p("Layout-first research into transparent candidate reconstruction of damaged manuscript pages.", "callout"),
        p("CURRENTLY WORKS", "h2"),
        bullet("IIIF ingestion, provenance, rights fields and database registration."),
        bullet("Mergen segmentation, source-coordinate masks and local inspection."),
        bullet("Deterministic artificial damage and layout-survival evaluation."),
        p("DOES NOT YET WORK", "h2"),
        bullet("Retrieval, same-manuscript matching, reconstruction candidates, expert review, export or production deployment."),
        p("CURRENT BLOCKERS", "h2"),
        bullet("Durable artifact storage, human review of flagged segmentation, rights approval, corpus diversity and a finished evaluation rubric."),
        p("NEXT RECOMMENDED MOVE", "h2"),
        bullet("Design Targeted Training Corpus Expansion Batch 02 after storage, quality and rights gates."),
        p("EXTERNAL COLLABORATIONS", "h2"),
        bullet("Use Andrew for candidate text identification and provenance; investigate Google for same-manuscript retrieval. Keep both behind university-controlled evaluation and human approval."),
        Spacer(1, 8),
        card("The sentence to use in meetings", "We are not building a machine that declares the lost page. We are building an evidence-preserving system that proposes and compares scholarly candidates.", PALE_AMBER, AMBER, 168 * mm),
        Spacer(1, 10),
        NotebookBox("My next three actions", 57 * mm, TEAL),
        PageBreak(),
    ]

    # Sources
    story += chapter("21", "Repository reading trail", "These are the source-of-truth documents used to build the guide.")
    refs = [
        ("README.md", "Current public project overview, setup, implemented and unimplemented scope."),
        ("docs/ARCHITECTURE.md", "Current component view, data flow, storage and evidence boundaries."),
        ("docs/IMPLEMENTATION_STATUS_2026-10.md", "Planned-versus-implemented subsystem comparison."),
        ("ROADMAP_STATUS.md", "Milestones, evidence files and next action per area."),
        ("NEXT_ACTIONS.md", "Current recommended decision and acceptance criteria."),
        ("docs/17_training_corpus_expansion_batch_01.md", "70-page Batch 01 selection, acquisition and segmentation gate."),
        ("docs/19a_corpus_diversity_audit.md", "85-page corpus composition, layout classes and gaps."),
        ("docs/20_artificial_fragment_experiment_v03.md", "156-task structured-damage experiment and limits."),
        ("docs/06_risks_and_decisions.md", "Risk register and governance decisions."),
        ("docs/04_evaluation_plan.md", "Evaluation concepts and future expert review needs."),
    ]
    story += [status_table([(name, "SOURCE", note) for name, note in refs])]
    story += [
        Spacer(1, 12),
        card("Version note", "This guide describes the repository as inspected on 26 October 2026. It is a study aid, not a replacement for live milestone documents or specialist review.", PALE_BLUE, BLUE, 168 * mm),
        Spacer(1, 16),
        p("You are allowed to feel lost before you draw the map.", "quote"),
        p("Now you have the map.", "chapter"),
    ]
    return story


def build_pdf(output: Path = OUTPUT) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=21 * mm,
        bottomMargin=18 * mm,
        title="Fragment Autocomplete Project Study Guide",
        author="Fragment Autocomplete project",
        subject="Notebook-friendly guide to the project pipeline, status and decisions",
        creator="scripts/build_project_study_guide.py",
    )
    doc.build(build_story(), onFirstPage=draw_cover, onLaterPages=draw_page)
    return output


if __name__ == "__main__":
    print(build_pdf())
