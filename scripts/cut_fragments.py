#!/usr/bin/env python3
"""Cut complete page images into three torn pieces each (synthetic fragments for matching tests).

  python scripts/cut_fragments.py --sources data/raw/seshat_samples \
      --output outputs/cut_fragments/seshat_v1 --seed seshat-v1

Writes, per page and piece: ``<page_id>/piece_<k>.jpg`` (the piece photographed on a neutral
background), ``<page_id>/piece_<k>_survival.png`` (255 = piece material), and a
``manifest.json`` with page checksums, cut parameters and every piece's bounding box in the
normalised leaf frame. Pieces are synthetic comparators, not historical fragments.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from src.evaluation.cut_pieces import VERSION, cut_page  # noqa: E402

Image.MAX_IMAGE_PIXELS = 400_000_000
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def page_id(path: Path) -> str:
    """Stable short id from the file name: the leading group code (e.g. 'A_1') when present."""
    m = re.match(r"^([A-Z])_(\d+)", path.stem)
    return f"{m.group(1)}{m.group(2)}" if m else re.sub(r"[^A-Za-z0-9]+", "-", path.stem)[:24]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="cut-v1")
    parser.add_argument("--profile", choices=("clean", "realistic"), default="clean",
                        help="realistic: aged leaf, worn and trimmed edges, 2-3 combined damages, archive photography")
    args = parser.parse_args()
    src, out = Path(args.sources), Path(args.output)
    files = sorted(p for p in src.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if not files:
        raise SystemExit(f"no images in {src}")
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"version": VERSION, "profile": args.profile, "seed": args.seed, "pages": [],
                "note": "Synthetic pieces cut from complete pages; not historical fragments."}
    for f in files:
        pid = page_id(f)
        digest = hashlib.sha256(f.read_bytes()).hexdigest()
        with Image.open(f) as im:
            pieces, meta = cut_page(im, f"{args.seed}:{pid}:{digest[:12]}", profile=args.profile)
        folder = out / pid
        folder.mkdir(exist_ok=True)
        entries = []
        for p in pieces:
            p.photo.save(folder / f"piece_{p.index}.jpg", quality=92)
            p.survival.save(folder / f"piece_{p.index}_survival.png")
            entries.append({**p.record(), "image": f"{pid}/piece_{p.index}.jpg",
                            "survival": f"{pid}/piece_{p.index}_survival.png",
                            "photo_size": list(p.photo.size)})
        manifest["pages"].append({"page_id": pid, "source_file": f.name, "source_sha256": digest, **meta,
                                  "pieces": entries})
        print(f"{pid}: {meta['layout']}, {len(pieces)} pieces, areas "
              f"{[e['area_fraction'] for e in entries]}, ink {[e['ink_fraction'] for e in entries]}")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"\n{sum(len(p['pieces']) for p in manifest['pages'])} pieces from {len(files)} pages -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
