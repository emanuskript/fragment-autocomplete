#!/usr/bin/env python3
"""Export the metadata-first project status dashboard as a durable PDF."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.frontend.project_status import load_project_snapshot  # noqa: E402


INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#667085")
TEAL = colors.HexColor("#279989")
CYAN = colors.HexColor("#3D8CA6")
AMBER = colors.HexColor("#E6A83B")
CORAL = colors.HexColor("#E66855")
PALE = colors.HexColor("#F4F2EC")
RULE = colors.HexColor("#D9DCE2")
WHITE = colors.white


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=25,
            leading=29,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=7 * mm,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=11,
            leading=16,
            textColor=MUTED,
            spaceAfter=6 * mm,
        ),
        "h1": ParagraphStyle(
            "Heading1Custom",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=21,
            textColor=INK,
            spaceBefore=3 * mm,
            spaceAfter=4 * mm,
        ),
        "h2": ParagraphStyle(
            "Heading2Custom",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=INK,
            spaceBefore=2 * mm,
            spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "BodyCustom",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=INK,
            spaceAfter=3 * mm,
        ),
        "small": ParagraphStyle(
            "SmallCustom",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.7,
            leading=10.5,
            textColor=MUTED,
        ),
        "cell": ParagraphStyle(
            "Cell",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10.5,
            textColor=INK,
        ),
        "cell_bold": ParagraphStyle(
            "CellBold",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10.5,
            textColor=INK,
        ),
        "white": ParagraphStyle(
            "White",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=WHITE,
        ),
    }


def paragraph(value: object, style: ParagraphStyle) -> Paragraph:
    text = str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(text, style)


def draw_page(canvas, doc) -> None:  # type: ignore[no-untyped-def]
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(TEAL)
    canvas.setLineWidth(1.4)
    canvas.line(18 * mm, height - 15 * mm, width - 18 * mm, height - 15 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 9 * mm, "Fragment Autocomplete · archived project-status dashboard")
    canvas.drawRightString(width - 18 * mm, 9 * mm, f"{doc.page}")
    canvas.restoreState()


def metric_table(snapshot: dict, s: dict[str, ParagraphStyle]) -> Table:
    items = [
        (snapshot["corpus"]["pages"], "corpus pages"),
        (snapshot["corpus"]["valid_masks"], "layout masks"),
        (snapshot["matrix"]["row_count"], "matrix rows"),
        (snapshot["matrix"]["implemented_operators"], "active operators"),
        (snapshot["database"]["table_count"], "schema tables"),
    ]
    cells = []
    for value, label in items:
        cells.append(
            [
                paragraph(f"{value:,}", s["h1"]),
                paragraph(label, s["small"]),
            ]
        )
    table = Table([cells], colWidths=[34 * mm] * len(cells))
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF6F4")),
                ("BOX", (0, 0), (-1, -1), 0.5, RULE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
            ]
        )
    )
    return table


def status_color(status: str) -> colors.Color:
    if status == "implemented":
        return TEAL
    if status == "partial":
        return AMBER
    return CORAL


def build_pdf(output: Path) -> None:
    snapshot = load_project_snapshot(ROOT)
    s = styles()
    output.parent.mkdir(parents=True, exist_ok=True)

    doc = BaseDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=22 * mm,
        bottomMargin=17 * mm,
        title="Fragment Autocomplete Project Status Dashboard",
        author="Fragment Autocomplete project",
        subject="Archived metadata-first project status as of 2026-11-09",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
    doc.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=draw_page)])

    story = [
        Spacer(1, 8 * mm),
        paragraph("PROJECT STATUS · 2026-11-09", s["small"]),
        paragraph("Fragment Autocomplete: the evidence observatory", s["title"]),
        paragraph(snapshot["headline"], s["subtitle"]),
        metric_table(snapshot, s),
        Spacer(1, 7 * mm),
        paragraph("The plain-English version", s["h1"]),
        paragraph(
            "The project has built the laboratory bench. It can collect manuscript pages, preserve where they came from, "
            "segment layout with Mergen/eManuSkript, store regions, apply controlled synthetic damage, and measure what "
            "survives. It has not yet built retrieval or a system that proposes missing historical content.",
            s["body"],
        ),
        Table(
            [[paragraph("Evidence boundary", s["white"]), paragraph("Synthetic loss is experiment truth; model masks are not expert ground truth; future reconstructions must remain candidate scholarly hypotheses.", s["cell"])]],
            colWidths=[40 * mm, 130 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), INK),
                    ("BACKGROUND", (1, 0), (1, 0), PALE),
                    ("BOX", (0, 0), (-1, -1), 0.5, RULE),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("PADDING", (0, 0), (-1, -1), 3 * mm),
                ]
            ),
        ),
        Spacer(1, 7 * mm),
        paragraph("End-to-end project state", s["h1"]),
    ]

    pipeline_rows = [[paragraph("Stage", s["cell_bold"]), paragraph("State", s["cell_bold"]), paragraph("What exists", s["cell_bold"])]]
    for stage in snapshot["pipeline"]:
        pipeline_rows.append(
            [
                paragraph(stage["name"], s["cell_bold"]),
                paragraph(stage["status"], s["cell_bold"]),
                paragraph(stage["detail"], s["cell"]),
            ]
        )
    pipeline_table = Table(pipeline_rows, colWidths=[47 * mm, 25 * mm, 98 * mm], repeatRows=1)
    pipeline_style = [
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("BOX", (0, 0), (-1, -1), 0.5, RULE),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 2.3 * mm),
    ]
    for index, stage in enumerate(snapshot["pipeline"], 1):
        pipeline_style.append(("TEXTCOLOR", (1, index), (1, index), status_color(stage["status"])))
    pipeline_table.setStyle(TableStyle(pipeline_style))
    story.extend([pipeline_table, PageBreak(), paragraph("What the project actually implemented", s["h1"])])

    for item in snapshot["ledger"]:
        block = Table(
            [
                [paragraph(item["name"], s["cell_bold"]), paragraph(item["status"], s["cell_bold"])],
                [paragraph(item["what"], s["cell"]), paragraph("Evidence: " + ", ".join(item["evidence"]), s["small"])],
                [paragraph("Boundary: " + item["boundary"], s["small"]), ""],
            ],
            colWidths=[116 * mm, 54 * mm],
        )
        block.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF1F3")),
                    ("TEXTCOLOR", (1, 0), (1, 0), status_color(item["status"])),
                    ("SPAN", (0, 2), (1, 2)),
                    ("BOX", (0, 0), (-1, -1), 0.45, RULE),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("PADDING", (0, 0), (-1, -1), 2.2 * mm),
                ]
            )
        )
        story.extend([KeepTogether([block, Spacer(1, 2.5 * mm)])])

    story.extend([PageBreak(), paragraph("Controlled experiments", s["h1"])])
    experiment_rows = [[paragraph("Version", s["cell_bold"]), paragraph("Tasks", s["cell_bold"]), paragraph("Measurements", s["cell_bold"]), paragraph("Meaning", s["cell_bold"])]]
    for item in snapshot["experiments"]:
        experiment_rows.append(
            [
                paragraph(f"{item['version']} · {item['title']}", s["cell_bold"]),
                paragraph(item["tasks"], s["cell"]),
                paragraph(item["observations"], s["cell"]),
                paragraph(item["finding"], s["cell"]),
            ]
        )
    experiments = Table(experiment_rows, colWidths=[41 * mm, 23 * mm, 30 * mm, 76 * mm], repeatRows=1)
    experiments.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("BOX", (0, 0), (-1, -1), 0.5, RULE),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 2.4 * mm),
            ]
        )
    )
    story.extend(
        [
            experiments,
            Spacer(1, 7 * mm),
            paragraph("Jeremy’s matrix: policy versus implementation", s["h1"]),
            paragraph(
                f"The adapter preserves {snapshot['matrix']['row_count']} matrix rows and {snapshot['matrix']['named_damage_types']} named damage types. "
                f"Only {snapshot['matrix']['implemented_operators']} operators currently generate real artifacts; "
                f"{snapshot['matrix']['unimplemented_operators']} remain explicit engineering work. The S1–S4 semantic language still requires specialist validation.",
                s["body"],
            ),
            PageBreak(),
            paragraph("Next steps", s["h1"]),
            paragraph("The shortest honest route from laboratory bench to scholarly tool:", s["subtitle"]),
        ]
    )

    for step in snapshot["next_steps"]:
        item = Table(
            [
                [paragraph(step["priority"], s["white"]), paragraph(step["title"], s["cell_bold"])],
                ["", paragraph(step["kind"].upper(), s["small"])],
                ["", paragraph(step["detail"], s["cell"])],
            ],
            colWidths=[14 * mm, 156 * mm],
        )
        item.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), TEAL),
                    ("SPAN", (0, 0), (0, -1)),
                    ("VALIGN", (0, 0), (0, -1), "MIDDLE"),
                    ("VALIGN", (1, 0), (1, -1), "TOP"),
                    ("BOX", (0, 0), (-1, -1), 0.5, RULE),
                    ("PADDING", (0, 0), (-1, -1), 2.5 * mm),
                ]
            )
        )
        story.extend([KeepTogether([item, Spacer(1, 3 * mm)])])

    story.extend(
        [
            Spacer(1, 5 * mm),
            Table(
                [[paragraph("Meeting sentence", s["white"]), paragraph("We have the ingestion, provenance, layout, storage, and controlled-damage laboratory; retrieval and candidate reconstruction are the next research milestones, and all future outputs must remain evidence-linked hypotheses.", s["cell"])]],
                colWidths=[38 * mm, 132 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (0, 0), INK),
                        ("BACKGROUND", (1, 0), (1, 0), PALE),
                        ("BOX", (0, 0), (-1, -1), 0.5, RULE),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("PADDING", (0, 0), (-1, -1), 3 * mm),
                    ]
                ),
            ),
        ]
    )
    doc.build(story)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output/pdf/Fragment_Autocomplete_Status_Dashboard_2026-11-09.pdf",
    )
    args = parser.parse_args()
    build_pdf(args.output.resolve())
    print(args.output.resolve())


if __name__ == "__main__":
    main()
