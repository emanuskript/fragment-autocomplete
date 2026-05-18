#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
import streamlit as st


ROOT = Path(__file__).resolve().parent.parent
SMOKE_TEST_ID = "segmentation_smoke_test_v0_1"


def db_connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ.get("FRAGMENT_DB_HOST", "localhost"),
        port=os.environ.get("FRAGMENT_DB_PORT", "55432"),
        dbname=os.environ.get("FRAGMENT_DB_NAME", "fragment"),
        user=os.environ.get("FRAGMENT_DB_USER", "fragment"),
        password=os.environ.get("FRAGMENT_DB_PASSWORD", "fragment_dev_password"),
    )


@st.cache_data(ttl=5)
def fetch_runs() -> list[dict[str, Any]]:
    query = """
    SELECT
      sr.id::text AS segmentation_run_id,
      sr.parameters->>'sample_id' AS sample_id,
      sr.parameters->>'sample_kind' AS sample_kind,
      sr.image_asset_id::text AS image_asset_id,
      sr.fragment_id::text AS fragment_id,
      COALESCE(sr.parameters->>'db_canvas_id', ia.canvas_id::text) AS canvas_id,
      sr.model_name,
      sr.model_source,
      sr.status,
      sr.output_path,
      sr.output_format,
      sr.parameters,
      sr.confidence_summary,
      sr.created_at,
      sr.completed_at,
      ia.local_path AS image_local_path,
      COALESCE(sr.raw_output->>'overlay_path', sr.parameters->>'overlay_path') AS overlay_path,
      COALESCE(sr.parameters->>'source_url', sr.raw_output->>'source_url') AS source_url,
      COUNT(lr.id)::int AS region_count,
      MIN(lr.confidence)::float AS confidence_min,
      AVG(lr.confidence)::float AS confidence_mean,
      MAX(lr.confidence)::float AS confidence_max,
      ARRAY_REMOVE(ARRAY_AGG(DISTINCT lr.label ORDER BY lr.label), NULL) AS labels
    FROM segmentation_run sr
    LEFT JOIN image_asset ia ON ia.id = sr.image_asset_id
    LEFT JOIN layout_region lr ON lr.segmentation_run_id = sr.id
    WHERE sr.parameters->>'smoke_test_id' = %s
    GROUP BY sr.id, ia.local_path, ia.canvas_id
    ORDER BY sr.parameters->>'sample_id'
    """
    with db_connect() as conn, conn.cursor() as cur:
        cur.execute(query, (SMOKE_TEST_ID,))
        rows = cur.fetchall()
        columns = [desc.name for desc in cur.description]
    return [dict(zip(columns, row)) for row in rows]


@st.cache_data(ttl=5)
def fetch_regions(segmentation_run_id: str) -> pd.DataFrame:
    query = """
    SELECT
      lr.label,
      lr.label_id,
      lr.confidence::float AS confidence,
      lr.reading_order_index,
      lr.region_area_px::float AS region_area_px,
      ST_AsText(lr.bbox_geom) AS bbox_wkt,
      ST_AsText(lr.region_geom) AS region_wkt,
      ST_AsText(ST_Envelope(lr.bbox_geom)) AS bbox_envelope_wkt,
      lr.raw_region
    FROM layout_region lr
    WHERE lr.segmentation_run_id = %s
    ORDER BY lr.reading_order_index NULLS LAST, lr.id
    """
    with db_connect() as conn, conn.cursor() as cur:
        cur.execute(query, (segmentation_run_id,))
        rows = cur.fetchall()
        columns = [desc.name for desc in cur.description]
    records = []
    for row in rows:
        item = dict(zip(columns, row))
        raw_region = item.pop("raw_region")
        item["raw_region_preview"] = json.dumps(raw_region, ensure_ascii=False)[:280]
        item["raw_region"] = raw_region
        records.append(item)
    return pd.DataFrame(records)


def resolve_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    return (ROOT / candidate).resolve()


def image_exists(path_value: str | None) -> tuple[Path | None, bool]:
    path = resolve_path(path_value)
    return path, bool(path and path.exists())


def render_metadata(run: dict[str, Any]) -> None:
    st.subheader("Segmentation Run Metadata")
    left, right = st.columns(2)
    with left:
        st.markdown(f"- `segmentation_run_id`: `{run['segmentation_run_id']}`")
        st.markdown(f"- `sample_id`: `{run['sample_id']}`")
        st.markdown(f"- `sample_kind`: `{run['sample_kind']}`")
        st.markdown(f"- `image_asset_id`: `{run['image_asset_id']}`")
        st.markdown(f"- `canvas_id`: `{run.get('canvas_id') or 'n/a'}`")
        st.markdown(f"- `fragment_id`: `{run.get('fragment_id') or 'n/a'}`")
        st.markdown(f"- `model_name`: `{run['model_name']}`")
        st.markdown(f"- `model_source`: `{run['model_source']}`")
    with right:
        st.markdown(f"- `status`: `{run['status']}`")
        st.markdown(f"- `output_path`: `{run['output_path']}`")
        st.markdown(f"- `output_format`: `{run['output_format']}`")
        st.markdown(f"- `created_at`: `{run['created_at']}`")
        st.markdown(f"- `completed_at`: `{run['completed_at']}`")
        st.markdown(f"- `source_url`: {run.get('source_url') or 'n/a'}")

    with st.expander("Parameters / provenance JSON", expanded=False):
        st.json(run["parameters"])
    with st.expander("Confidence summary JSON", expanded=False):
        st.json(run["confidence_summary"])


def render_images(run: dict[str, Any]) -> None:
    st.subheader("Images")
    original_path, original_exists = image_exists(run.get("image_local_path"))
    overlay_path, overlay_exists = image_exists(run.get("overlay_path"))
    left, right = st.columns(2)
    with left:
        st.markdown("**Original local image**")
        if original_exists and original_path is not None:
            st.image(str(original_path), use_container_width=True)
            st.caption(str(original_path))
        else:
            st.warning(f"Original image missing: {run.get('image_local_path')}")
    with right:
        st.markdown("**Saved segmentation overlay**")
        if overlay_exists and overlay_path is not None:
            st.image(str(overlay_path), use_container_width=True)
            st.caption(str(overlay_path))
        else:
            st.warning(f"Overlay image missing: {run.get('overlay_path')}")


def render_region_summary(run: dict[str, Any], regions_df: pd.DataFrame) -> None:
    st.subheader("Layout Region Summary")
    labels = run.get("labels") or []
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Region count", int(run.get("region_count") or 0))
    col2.metric("Min confidence", f"{(run.get('confidence_min') or 0):.3f}")
    col3.metric("Mean confidence", f"{(run.get('confidence_mean') or 0):.3f}")
    col4.metric("Max confidence", f"{(run.get('confidence_max') or 0):.3f}")
    st.markdown("**Detected labels**")
    st.write(", ".join(labels) if labels else "No labels found.")
    if not regions_df.empty:
        label_counts = regions_df["label"].value_counts().rename_axis("label").reset_index(name="count")
        st.dataframe(label_counts, use_container_width=True, hide_index=True)


def render_region_table(regions_df: pd.DataFrame) -> None:
    st.subheader("Layout Regions")
    if regions_df.empty:
        st.info("No layout regions stored for this run.")
        return
    display_columns = [
        "label",
        "label_id",
        "confidence",
        "reading_order_index",
        "region_area_px",
        "bbox_wkt",
        "region_wkt",
        "raw_region_preview",
    ]
    st.dataframe(regions_df[display_columns], use_container_width=True, hide_index=True)
    with st.expander("Raw region metadata", expanded=False):
        selected_index = st.number_input(
            "Row index",
            min_value=0,
            max_value=len(regions_df) - 1,
            value=0,
            step=1,
            key="raw_region_index",
        )
        raw_region = regions_df.iloc[int(selected_index)]["raw_region"]
        st.json(raw_region)


def main() -> None:
    st.set_page_config(page_title="Fragment Autocomplete Segmentation Viewer", layout="wide")
    st.title("Fragment Autocomplete — Minimal Segmentation Viewer")
    st.caption("Local read-only viewer for the two stored segmentation smoke-test samples.")

    try:
        runs = fetch_runs()
    except Exception as exc:  # pragma: no cover - streamlit error display
        st.error(f"Failed to query PostgreSQL/PostGIS: {exc}")
        st.stop()

    if not runs:
        st.warning("No stored smoke-test segmentation runs were found.")
        st.stop()

    sample_options = {run["sample_id"]: run for run in runs}
    selected_sample = st.sidebar.selectbox("Sample", list(sample_options.keys()))
    run = sample_options[selected_sample]
    regions_df = fetch_regions(run["segmentation_run_id"])

    st.sidebar.markdown("### Stored smoke-test samples")
    for sample_id, sample_run in sample_options.items():
        st.sidebar.markdown(f"- `{sample_id}` ({sample_run['sample_kind']})")

    render_images(run)
    render_metadata(run)
    render_region_summary(run, regions_df)
    render_region_table(regions_df)


if __name__ == "__main__":
    main()
