#!/usr/bin/env python3
"""Read-only Streamlit observatory for the complete project implementation state."""

from __future__ import annotations

from html import escape
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.frontend.project_status import exportable_snapshot, load_project_snapshot


NAV_ITEMS = [
    "Overview",
    "Damage matrix",
    "Segmentation",
    "Storage & provenance",
    "Experiments",
    "Implementation ledger",
    "Next steps",
]


def fmt(value: Any) -> str:
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def load_css() -> None:
    css = (ROOT / "src/frontend/dashboard.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def page_header(section: str, title: str, finding: str) -> None:
    st.markdown(
        f"""
        <div class="page-title-row">
          <div>
            <div class="eyebrow">{escape(section)} · status snapshot 2026-11-09</div>
            <h1>{escape(title)}</h1>
            <div class="finding">{escape(finding)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def truth_note(title: str, body: str) -> None:
    st.markdown(
        f'<div class="truth-note"><div><strong>{escape(title)}</strong><p>{escape(body)}</p></div></div>',
        unsafe_allow_html=True,
    )


def kpi_strip(items: list[tuple[str, Any, str]]) -> None:
    cells = "".join(
        (
            f'<div class="kpi-cell{" kpi-accent" if index == 1 else ""}">'
            f'<div class="kpi-label">{escape(label)}</div>'
            f'<div class="kpi-value">{escape(fmt(value))}'
            f'<span class="kpi-unit">{escape(unit)}</span></div>'
            "</div>"
        )
        for index, (label, value, unit) in enumerate(items)
    )
    st.markdown(
        f'<div class="kpi-strip" style="--kpi-count:{len(items)}">{cells}</div>',
        unsafe_allow_html=True,
    )


def section_kicker(title: str, note: str = "") -> None:
    st.markdown(
        f'<div class="section-kicker"><h2>{escape(title)}</h2><span>{escape(note)}</span></div>',
        unsafe_allow_html=True,
    )


def pipeline_html(stages: list[dict[str, str]]) -> str:
    blocks = []
    for index, stage in enumerate(stages, 1):
        status = stage["status"]
        blocks.append(
            f'<div class="pipeline-stage {escape(status.replace(" ", "-"))}">'
            f'<div class="pipeline-index">{index:02d}</div>'
            f'<div class="pipeline-name">{escape(stage["name"])}</div>'
            f'<div class="pipeline-detail">{escape(stage["detail"])}</div>'
            f'<div class="status-label">{escape(status.title())}</div>'
            "</div>"
        )
    return '<div class="pipeline">' + "".join(blocks) + "</div>"


def bar_list(rows: list[dict[str, Any]], label_key: str, value_key: str, limit: int | None = None) -> None:
    selected = rows[:limit] if limit else rows
    maximum = max((float(row[value_key]) for row in selected), default=1.0)
    html = []
    for row in selected:
        width = 100 * float(row[value_key]) / maximum if maximum else 0
        html.append(
            '<div class="bar-row">'
            f'<div class="bar-label" title="{escape(str(row[label_key]))}">{escape(str(row[label_key]))}</div>'
            f'<div class="bar-track" aria-hidden="true"><div class="bar-fill" style="width:{width:.2f}%"></div></div>'
            f'<div class="bar-value">{escape(fmt(row[value_key]))}</div>'
            "</div>"
        )
    st.markdown('<div class="bar-list">' + "".join(html) + "</div>", unsafe_allow_html=True)


def sidebar(snapshot: dict[str, Any]) -> str:
    st.sidebar.markdown(
        """
        <div class="product-lockup">
          <span class="product-mark" aria-hidden="true"></span>
          <div>
            <div class="product-name">Fragment Autocomplete</div>
            <div class="product-scope">Evidence observatory</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.radio(
        "Project views",
        NAV_ITEMS,
        key="sidebar_nav",
        on_change=sync_from_sidebar,
        label_visibility="collapsed",
    )
    st.sidebar.markdown(
        f"""
        <div class="sidebar-foot">
          <strong>Current scope</strong><br>
          Committed metadata snapshot<br>
          As of {escape(snapshot['as_of'])}<br><br>
          No live database or ignored image corpus is required.
        </div>
        """,
        unsafe_allow_html=True,
    )
    return st.session_state["nav_page"]


def sync_from_sidebar() -> None:
    st.session_state["nav_page"] = st.session_state["sidebar_nav"]


def sync_from_mobile() -> None:
    st.session_state["nav_page"] = st.session_state["mobile_nav"]


def mobile_navigation() -> None:
    with st.container(key="mobile_nav_control"):
        st.selectbox(
            "Project view",
            NAV_ITEMS,
            key="mobile_nav",
            on_change=sync_from_mobile,
        )


def render_overview(snapshot: dict[str, Any]) -> None:
    page_header("Project overview", "Where development stands today", snapshot["headline"])
    truth_note(
        "Plain English",
        (
            "The project can collect manuscript pages, retain their provenance, segment page layout with Mergen, "
            "store regions, create controlled synthetic damage, and measure what survives. It cannot yet retrieve "
            "comparators or propose missing content."
        ),
    )
    kpi_strip(
        [
            ("Corpus pages", snapshot["corpus"]["pages"], "pages"),
            ("Mergen masks", snapshot["corpus"]["valid_masks"], "regions"),
            ("Jeremy matrix", snapshot["matrix"]["row_count"], "rows"),
            ("Active damage operators", snapshot["matrix"]["implemented_operators"], "of 17"),
            ("Database schema", snapshot["database"]["table_count"], "tables"),
        ]
    )

    section_kicker("End-to-end evidence pipeline", "Implemented, partial, and future are shown separately")
    st.markdown(pipeline_html(snapshot["pipeline"]), unsafe_allow_html=True)

    section_kicker("The evidence boundary", "What each layer is allowed to claim")
    st.markdown(
        """
        <div class="evidence-chain">
          <div class="evidence-node"><small>01 · observed</small><strong>Source pixels + metadata</strong><p>Upstream images, identifiers, rights text, checksums and raw IIIF records.</p></div>
          <div class="evidence-node"><small>02 · model-derived</small><strong>Mergen layout evidence</strong><p>Predicted regions, labels, confidence values and source-sized masks.</p></div>
          <div class="evidence-node"><small>03 · synthetic</small><strong>Controlled experiment truth</strong><p>Known artificial damage and hidden complete targets used only for evaluation or supervised experiments.</p></div>
          <div class="evidence-node"><small>04 · future inference</small><strong>Candidate hypotheses</strong><p>Multiple possible reconstructions with provenance and uncertainty—not recovered historical truth.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="meeting-line">
          <strong>THE 20-SECOND MEETING VERSION</strong>
          Today we have the laboratory bench: reliable ingestion, provenance, layout segmentation, storage, synthetic
          damage and reproducible evaluation. We have not yet built the machine that searches for comparators or proposes
          missing manuscript content. Jeremy's matrix now tells us which synthetic conditions are meaningful; three of its
          seventeen damage operators can currently generate samples.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.download_button(
        "Download status snapshot",
        data=json.dumps(exportable_snapshot(snapshot), indent=2, ensure_ascii=False) + "\n",
        file_name="fragment_autocomplete_status_2026-11-09.json",
        mime="application/json",
        help="Exports the same committed evidence summarized in this dashboard.",
    )


def render_damage_matrix(snapshot: dict[str, Any]) -> None:
    matrix = snapshot["matrix"]
    page_header(
        "Synthetic data",
        "Jeremy's damage matrix",
        "The matrix is a decision policy; the operator registry is the implementation. They are related, but not the same thing.",
    )
    kpi_strip(
        [
            ("Matrix rows", matrix["row_count"], "content × damage"),
            ("Damage types", matrix["named_damage_types"], "registered"),
            ("Content types", matrix["content_types"], "registered"),
            ("Implemented operators", matrix["implemented_operators"], "of 17"),
            ("Rows needing review", len(matrix["rows_needing_review"]), "source rows"),
        ]
    )

    section_kicker("Implementation coverage", "Every damage type is registered; only real operators count as implemented")
    segments = "".join(
        '<span class="coverage-segment on"></span>' if index < matrix["implemented_operators"] else '<span class="coverage-segment"></span>'
        for index in range(matrix["named_damage_types"])
    )
    st.markdown(
        f'<div class="coverage-track" aria-label="3 of 17 damage operators implemented">{segments}</div>'
        '<div class="coverage-caption">3 implemented material-loss operators · 14 explicitly pending</div>',
        unsafe_allow_html=True,
    )

    implemented = [operator for operator in matrix["operators"] if operator["status"] == "implemented"]
    cards = "".join(
        (
            '<div class="operator-card">'
            f'<div class="operator-id">{escape(operator["damage_id"])}</div>'
            f'<strong>{escape(operator["damage_type"])}</strong>'
            f'<span>{escape(operator["operator"])} · {escape(operator["visual_class"])}</span>'
            "</div>"
        )
        for operator in implemented
    )
    st.markdown(f'<div class="operator-grid">{cards}</div>', unsafe_allow_html=True)

    truth_note(
        "These are procedural damage operators, not LLM agents",
        (
            "D2-01 creates an interior hole, D2-02 a straight edge loss, and D2-03 an irregular edge tear. "
            "They reuse a selected Mergen content mask for calibration. No VLM, diffusion model, Qwen, DINO, or "
            "agent framework generates these samples."
        ),
    )

    decision_rows = [
        {"decision": decision or "missing", "count": count}
        for decision, count in matrix["decisions"].items()
    ]
    section_kicker("Source decision totals", "Four severities per matrix row")
    bar_list(sorted(decision_rows, key=lambda row: row["count"], reverse=True), "decision", "count")

    section_kicker("Operator registry", "Pending effects need their own optical, material, or deformation models")
    st.dataframe(
        pd.DataFrame(matrix["operators"]),
        use_container_width=True,
        hide_index=True,
        column_order=["damage_id", "damage_type", "visual_class", "operator", "status"],
    )

    section_kicker("Decision matrix explorer", "Filters operate on 748 severity cells")
    rows = pd.DataFrame(matrix["rows"])
    filter_a, filter_b, filter_c = st.columns(3)
    with filter_a:
        content = st.selectbox("Content type", ["All"] + sorted(rows["content_type"].unique().tolist()))
    with filter_b:
        damage = st.selectbox("Damage type", ["All"] + sorted(rows["damage_type"].unique().tolist()))
    with filter_c:
        status = st.selectbox("Generation status", ["All"] + sorted(rows["generation_status"].unique().tolist()))
    if content != "All":
        rows = rows[rows["content_type"] == content]
    if damage != "All":
        rows = rows[rows["damage_type"] == damage]
    if status != "All":
        rows = rows[rows["generation_status"] == status]
    st.dataframe(rows, use_container_width=True, hide_index=True, height=430)

    st.markdown(
        """
        <div class="boundary-box"><strong>What remains unvalidated:</strong> S1-S4 use engineering area presets of
        2.5%, 12.5%, 35% and 65%. Those numbers are not yet specialist-approved translations of every qualitative note.
        The dashboard therefore reports implementation coverage and matrix decisions separately.</div>
        """,
        unsafe_allow_html=True,
    )


def render_segmentation(snapshot: dict[str, Any]) -> None:
    segmentation = snapshot["segmentation"]
    corpus = snapshot["corpus"]
    page_header(
        "Layout analysis",
        "Mergen segmentation",
        "The layout backbone is running and stored: 85 corpus pages produced 4,230 source-coordinate masks.",
    )
    kpi_strip(
        [
            ("Corpus pages", corpus["pages"], "segmented"),
            ("Successful pages", segmentation["successful_pages"], "validation + Batch 01"),
            ("Failed pages", segmentation["failed_pages"], "runner failures"),
            ("Layout regions", corpus["layout_regions"], "model-derived"),
            ("Zero detections", corpus["zero_detection_pages"], "pages retained"),
        ]
    )

    truth_note(
        "What the model does",
        (
            "The registered best_emanuskript_segmentation checkpoint predicts regions such as main script, glosses, "
            "initials, music, illustrations, borders and tables. The project stores every label, confidence, geometry, "
            "mask path, source checksum and inference setting. It does not infer missing text or pixels."
        ),
    )

    section_kicker("Validated runs", "Compact metadata; binaries remain outside Git")
    st.dataframe(pd.DataFrame(segmentation["runs"]), use_container_width=True, hide_index=True)

    section_kicker("Detected layout classes", "Combined validation and Batch 01 counts")
    bar_list(segmentation["labels"], "label", "count", limit=12)

    section_kicker("How a page moves through segmentation", "One inference path, reused by each corpus workflow")
    st.markdown(
        """
        <div class="evidence-chain">
          <div class="evidence-node"><small>01 · prepare</small><strong>Explicit input manifest</strong><p>Page identity, split, source path and checksum are fixed before inference.</p></div>
          <div class="evidence-node"><small>02 · infer</small><strong>Mergen checkpoint</strong><p>The isolated runner records model hash, device, threshold and image size.</p></div>
          <div class="evidence-node"><small>03 · restore</small><strong>Source coordinates</strong><p>Binary instance masks and geometries are returned to the original page frame.</p></div>
          <div class="evidence-node"><small>04 · store</small><strong>Regions + artifacts</strong><p>PostGIS stores geometry/provenance; the filesystem stores mask and overlay bytes.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f'<p class="mono-note">model sha256 · {escape(segmentation["model_sha256"])}</p>', unsafe_allow_html=True)


def render_storage(snapshot: dict[str, Any]) -> None:
    database = snapshot["database"]
    corpus = snapshot["corpus"]
    page_header(
        "Data architecture",
        "Storage, rights and provenance",
        "PostgreSQL/PostGIS stores identities, metadata and geometry; large binaries stay in ignored, checksum-addressed storage.",
    )
    kpi_strip(
        [
            ("Schema tables", database["table_count"], "total"),
            ("Operational tables", database["implemented_table_count"], "current workflows"),
            ("Future groundwork", database["future_table_count"], "schema only"),
            ("Corpus manuscripts", corpus["page_bearing_manuscripts"], "with pages"),
            ("Training approvals", 0, "current corpus"),
        ]
    )

    section_kicker("Where each kind of information lives", "The storage split is deliberate")
    st.markdown(
        """
        <div class="evidence-chain">
          <div class="evidence-node"><small>database</small><strong>PostgreSQL + PostGIS</strong><p>Stable IDs, source links, rights fields, JSON provenance, runs, tasks and geometry.</p></div>
          <div class="evidence-node"><small>tracked</small><strong>data/metadata</strong><p>Compact specifications, checksums, decisions, statistics and validation records.</p></div>
          <div class="evidence-node"><small>ignored</small><strong>data/raw + outputs</strong><p>Downloaded pages, masks, overlays, generated fragments and bulk experiment artifacts.</p></div>
          <div class="evidence-node"><small>external</small><strong>Model weights</strong><p>Mergen checkpoints remain outside Git and are accepted only when their hashes match the registry.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    truth_note(
        "Rights are a field, not an assumption",
        (
            "The current e-codices corpus records rights_review_status=pending_review and training_allowed=false. "
            "A visible IIIF image, a segmentation success, or repository access does not by itself change that field."
        ),
    )

    section_kicker("Database entity ledger", "Schema groundwork is not presented as a working feature")
    st.dataframe(pd.DataFrame(database["tables"]), use_container_width=True, hide_index=True, height=520)

    st.markdown(
        """
        <div class="boundary-box"><strong>Future-facing schema:</strong> reconstruction_job,
        reconstruction_candidate, retrieval_embedding, text_witness_link, evaluation_run and export_bundle exist so the
        data model has a controlled extension path. There is no running retrieval, reconstruction, CoMMA-linking, export,
        or expert-review service behind them yet.</div>
        """,
        unsafe_allow_html=True,
    )


def render_experiments(snapshot: dict[str, Any]) -> None:
    page_header(
        "Evaluation",
        "Controlled experiments and invariants",
        "The experiment line is reproducible and increasingly realistic, but it measures technical survival—not recovered meaning.",
    )
    kpi_strip(
        [
            ("Latest v0.3 tasks", 156, "validation tasks"),
            ("Region observations", 2424, "v0.3"),
            ("Determinism check", snapshot["determinism"]["compared_artifacts"], "artifacts"),
            ("Frozen files", snapshot["determinism"]["frozen_files"], "verified"),
            ("Historical reconstructions", 0, "performed"),
        ]
    )

    section_kicker("Experiment progression", "Each milestone preserves the previous one")
    rows = []
    for experiment in snapshot["experiments"]:
        rows.append(
            '<div class="experiment-row">'
            f'<div class="experiment-version">{escape(experiment["version"])}</div>'
            f'<div class="experiment-main"><strong>{escape(experiment["title"])}</strong><p>{escape(experiment["finding"])}</p></div>'
            f'<div class="experiment-stat"><strong>{escape(fmt(experiment["tasks"]))}</strong><small>tasks</small></div>'
            f'<div class="experiment-stat"><strong>{escape(fmt(experiment["observations"]))}</strong><small>observations</small></div>'
            "</div>"
        )
    st.markdown("".join(rows), unsafe_allow_html=True)

    section_kicker("What the checks actually prove", "No inflated claims")
    checks = [
        ("Topology", "Damage masks obey the intended structural constraints."),
        ("Calibration", "Requested synthetic area loss stays within the declared engineering tolerance."),
        ("Pixel preservation", "Surviving source pixels remain byte-equal to the complete input."),
        ("Split isolation", "Test pages stay frozen and manuscript identities do not cross splits."),
        ("Idempotence", "Identical reruns match rows and bytes instead of creating duplicates or timestamp churn."),
        ("Frozen invariants", "Historical tasks, files, rights fields and database rows remain unchanged."),
    ]
    for name, explanation in checks:
        st.markdown(f"**{name}.** {explanation}")

    st.markdown(
        """
        <div class="boundary-box"><strong>Not proved:</strong> that a synthetic shape is historically likely, that a
        model understands the lost content, or that a high survival score means the meaning can be recovered.</div>
        """,
        unsafe_allow_html=True,
    )


def render_ledger(snapshot: dict[str, Any]) -> None:
    page_header(
        "Implementation",
        "Everything implemented so far",
        "This ledger explains the repository by capability, with the file evidence and the boundary of each claim.",
    )
    implemented = sum(1 for item in snapshot["ledger"] if item["status"] == "implemented")
    partial = sum(1 for item in snapshot["ledger"] if item["status"] == "partial")
    kpi_strip(
        [
            ("Capability groups", len(snapshot["ledger"]), "documented"),
            ("Implemented", implemented, "groups"),
            ("Partial", partial, "group"),
            ("Future features", 4, "explicitly not built"),
        ]
    )

    for index, item in enumerate(snapshot["ledger"], 1):
        label = f"{index:02d} · {item['name']} — {item['status']}"
        with st.expander(label, expanded=index <= 2):
            st.markdown(item["what"])
            st.markdown(f"**Evidence boundary.** {item['boundary']}")
            st.markdown("**Repository evidence**")
            for path in item["evidence"]:
                st.code(path, language=None)

    st.markdown(
        """
        <div class="boundary-box"><strong>Explicitly not implemented:</strong> a production backend, job queue,
        retrieval index, same-manuscript search, candidate reconstruction model, VLM fine-tune, expert accept/reject
        workflow, export service, or Fragmentarium deployment.</div>
        """,
        unsafe_allow_html=True,
    )


def render_next_steps(snapshot: dict[str, Any]) -> None:
    page_header(
        "Roadmap",
        "Next steps, in the right order",
        "The immediate gate is scholarly review of the matrix pilot—not jumping straight to a reconstruction model.",
    )
    truth_note(
        "The next engineering action",
        (
            "After Jeremy reviews the current shapes, content mapping and S1-S4 interpretation, implement one "
            "appearance operator—preferably staining or fading—with a separate visibility-mask contract and tests."
        ),
    )

    rows = []
    for step in snapshot["next_steps"]:
        rows.append(
            '<div class="next-row">'
            f'<div class="next-priority">STEP {escape(step["priority"])}</div>'
            f'<div class="next-main"><strong>{escape(step["title"])}</strong><p>{escape(step["detail"])}</p></div>'
            f'<div class="next-kind">{escape(step["kind"])}</div>'
            "</div>"
        )
    st.markdown("".join(rows), unsafe_allow_html=True)

    section_kicker("Decision gates before model training", "Keep the experiment scientifically and legally usable")
    gates = [
        "Expert-review the four flagged segmentation pages and the existing zero-detection pages.",
        "Approve a source subset for training; current assets remain pending_review with training_allowed=false.",
        "Choose what the first model predicts: damage mask, visibility mask, retrieval score, or candidate pixels.",
        "Define an evaluation baseline and held-out test before fine-tuning any VLM or vision model.",
        "Keep evidence, synthetic targets, and candidate inference as separate data products.",
    ]
    for gate in gates:
        st.markdown(f"- {gate}")

    st.markdown(
        """
        <div class="meeting-line"><strong>IF SOMEONE ASKS “DOES IT RECONSTRUCT MANUSCRIPTS YET?”</strong>
        No. It currently prepares, segments, stores and stress-tests manuscript evidence under controlled synthetic
        damage. Retrieval and candidate reconstruction are the next major research layers, and any future output will be
        presented as a reviewable scholarly hypothesis with provenance and uncertainty.</div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="Fragment Autocomplete · Evidence Observatory",
        page_icon=None,
        layout="wide",
        initial_sidebar_state="auto",
    )
    load_css()
    try:
        snapshot = load_project_snapshot(ROOT)
    except Exception as exc:  # pragma: no cover - visible runtime failure state
        st.error(f"Could not assemble the committed status snapshot: {exc}")
        st.stop()

    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = NAV_ITEMS[0]
    if "sidebar_nav" not in st.session_state:
        st.session_state["sidebar_nav"] = st.session_state["nav_page"]
    if "mobile_nav" not in st.session_state:
        st.session_state["mobile_nav"] = st.session_state["nav_page"]

    selected = sidebar(snapshot)
    mobile_navigation()
    renderers = {
        "Overview": render_overview,
        "Damage matrix": render_damage_matrix,
        "Segmentation": render_segmentation,
        "Storage & provenance": render_storage,
        "Experiments": render_experiments,
        "Implementation ledger": render_ledger,
        "Next steps": render_next_steps,
    }
    renderers[selected](snapshot)


if __name__ == "__main__":
    main()
