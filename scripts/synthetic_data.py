#!/usr/bin/env python3
"""One entry point for matrix import, coverage planning and synthetic data generation."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.damage_matrix import import_matrix, plan, write_json  # noqa: E402

DEFAULT_MATRIX = ROOT / "data/metadata/jeremy_damage_matrix_v3.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    importer = actions.add_parser("import-matrix", help="Preserve CSV decisions and flag incomplete rows")
    importer.add_argument("--csv", type=Path, required=True)
    importer.add_argument("--output", type=Path, default=DEFAULT_MATRIX)
    for name in ("plan", "prepare-corpus", "generate", "demo"):
        action = actions.add_parser(name)
        action.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
        action.add_argument("--include-edge-cases", action="store_true")
        if name == "plan":
            action.add_argument("--content-id")
            action.add_argument("--output", type=Path)
        else:
            action.add_argument("--output", type=Path, required=True)
            if name == "prepare-corpus":
                action.add_argument("--split", choices=("train", "validation"), default="train")
                action.add_argument("--label", required=True, help="Exact stored Mergen label")
                action.add_argument("--content-id", required=True, help="Explicit mapping to Jeremy's content ID")
                action.add_argument("--limit", type=int, default=1)
            elif name == "generate":
                action.add_argument("--sources", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "import-matrix":
            matrix = import_matrix(args.csv)
            write_json(args.output, matrix)
            result = matrix["summary"]
        else:
            matrix = json.loads(args.matrix.read_text())
            if args.action == "plan":
                report = plan(matrix, content_id=args.content_id, include_edge_cases=args.include_edge_cases)
                if args.output:
                    write_json(args.output, report)
                result = report["counts"]
            elif args.action == "prepare-corpus":
                from src.evaluation.matrix_synthesis import prepare_corpus_sources
                plan(matrix, content_id=args.content_id)
                config = prepare_corpus_sources(ROOT, split=args.split, label=args.label,
                                                content_id=args.content_id, limit=args.limit)
                write_json(args.output, config)
                result = {"selected_pages": len(config["pages"]), "output": str(args.output)}
            else:
                from src.evaluation.matrix_synthesis import generate_dataset, make_demo
                if args.action == "demo":
                    base = args.output / "fixture"
                    config = make_demo(base)
                    output = args.output / "dataset"
                else:
                    config = json.loads(args.sources.read_text())
                    base, output = args.sources.resolve().parent, args.output
                report = generate_dataset(matrix, config, base, output,
                                          include_edge_cases=args.include_edge_cases)
                result = {k: report[k] for k in ("generated_count", "skip_counts", "training_performed")}
        print(json.dumps(result, indent=2))
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, f"Synthetic-data workflow failed: {exc}\n")


if __name__ == "__main__":
    main()
