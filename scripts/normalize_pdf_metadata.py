#!/usr/bin/env python3
"""Normalize shareable PDF metadata without changing rendered page content."""

from __future__ import annotations

import argparse
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def normalize_metadata(path: Path, title: str) -> None:
    reader = PdfReader(path)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)

    metadata = {
        key: str(value)
        for key, value in (reader.metadata or {}).items()
        if key not in {"/Title", "/Creator", "/Producer"}
    }
    metadata.update(
        {
            "/Title": title,
            "/Creator": "Fragment Autocomplete repository build",
            "/Producer": "pypdf metadata normalization",
        }
    )
    writer.add_metadata(metadata)

    temporary_path = path.with_name(f".{path.name}.tmp")
    with temporary_path.open("wb") as handle:
        writer.write(handle)
    temporary_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--title", required=True)
    args = parser.parse_args()

    if not args.pdf.is_file():
        parser.error(f"PDF does not exist: {args.pdf}")
    normalize_metadata(args.pdf, args.title)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
