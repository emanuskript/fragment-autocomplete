"""Import Jeremy's content/damage matrix without repairing or inventing decisions."""
from __future__ import annotations

from collections import Counter
import csv
from hashlib import sha256
import io
import json
from pathlib import Path

VERSION = "jeremy_matrix_adapter_v1"
DECISIONS = {
    "do not generate": "excluded",
    "generate for general training": "general",
    "generate as edge case": "edge_case",
}
# These are visual effects, not autonomous LLM agents or inferred historical causes.
OPERATORS = {
    "D2-01": ("Interior loss", "Absent", "internal_hole"),
    "D2-02": ("Straight edge loss", "Absent", "edge_loss"),
    "D2-03": ("Irregular edge loss", "Absent", "edge_tear"),
    "D2-04": ("Ink-following loss", "Absent", None),
    "D2-06": ("Surface coating", "Obscured", None),
    "D2-07": ("Adhesive tape", "Obscured", None),
    "D2-08": ("Discrete deposits", "Obscured", None),
    "D2-09": ("Staining / discolouration", "Obscured", None),
    "D2-10": ("Overwriting", "Obscured", None),
    "D2-11": ("Faded ink or pigment", "Degraded", None),
    "D2-12": ("Surface loss", "Degraded", None),
    "D2-13": ("Erasure", "Degraded", None),
    "D2-14": ("Offset / transfer", "Foreign signal", None),
    "D2-16": ("Corrosion haloes", "Foreign signal", None),
    "D2-17": ("Ink bleed", "Foreign signal", None),
    "D2-18": ("Folds and creases", "Distorted", None),
    "D2-19": ("Cockling / shrinkage", "Distorted", None),
}
# Engineering sampling presets, NOT numerical translations of every qualitative note.
AREA_PROXIES = {"S1": .025, "S2": .125, "S3": .35, "S4": .65}


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def immutable_write(path, data):
    """Identical reruns are no-ops; changed output requires a new version/path."""
    path = Path(path)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"refusing_to_overwrite_changed_artifact:{path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def write_json(path, value):
    immutable_write(path, (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode())


def import_matrix(path):
    path = Path(path)
    raw = path.read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    required = {"Content ID", "Content type", "Damage ID", "Damage type", "Visual class"}
    required |= {f"S{s} {field}" for s in range(1, 5)
                 for field in ("decision", "severity note", "example (Fragmentarium)")}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("matrix_missing_required_columns")
    rows, seen = [], set()
    for number, raw_row in enumerate(reader, 2):
        if None in raw_row or any(value is None for value in raw_row.values()):
            raise ValueError(f"malformed_csv_row:{number}")
        row = {key: value.strip() for key, value in raw_row.items()}
        errors = []
        for field in ("Content ID", "Content type", "Damage ID", "Damage type", "Visual class"):
            if not row[field]:
                errors.append(f"missing:{field}")
        damage_id = row["Damage ID"]
        operator = OPERATORS.get(damage_id)
        if damage_id and operator is None:
            errors.append("unknown_damage_id")
        if operator and (row["Damage type"], row["Visual class"]) != operator[:2]:
            errors.append("damage_taxonomy_conflict")
        key = (row["Content ID"], damage_id)
        if damage_id:
            if key in seen:
                raise ValueError(f"duplicate_matrix_key:{key}")
            seen.add(key)
        levels = {}
        for severity in AREA_PROXIES:
            decision = row[f"{severity} decision"]
            note = row[f"{severity} severity note"]
            level_errors = []
            if decision not in DECISIONS:
                level_errors.append("missing_or_unknown_decision")
            if not note:
                level_errors.append("missing_severity_note")
            levels[severity] = {
                "decision": decision, "cohort": DECISIONS.get(decision),
                "note": note, "example_url": row[f"{severity} example (Fragmentarium)"],
                "issues": level_errors,
            }
        rows.append({
            "source_row": number, "content_id": row["Content ID"], "content_type": row["Content type"],
            "damage_id": damage_id, "damage_type": row["Damage type"], "visual_class": row["Visual class"],
            "family": operator[2] if operator else None, "issues": errors, "levels": levels,
        })
    if not rows:
        raise ValueError("empty_damage_matrix")
    return {
        "version": VERSION,
        "source": {"filename": path.name, "sha256": sha256(raw).hexdigest(), "attribution": "Jeremy; supplied by project user"},
        "rows": rows,
        "summary": {
            "row_count": len(rows), "named_damage_types": len({r["damage_id"] for r in rows if r["damage_id"]}),
            "content_types": len({r["content_id"] for r in rows}),
            "rows_needing_review": [r["source_row"] for r in rows
                                    if r["issues"] or any(v["issues"] for v in r["levels"].values())],
            "decisions": dict(Counter(v["decision"] for r in rows for v in r["levels"].values())),
        },
    }


def plan(matrix, *, content_id=None, include_edge_cases=False):
    entries = []
    for row in matrix["rows"]:
        if content_id and row["content_id"] != content_id:
            continue
        for severity, level in row["levels"].items():
            issues = row["issues"] + level["issues"]
            if issues:
                status = "matrix_review_required"
            elif level["cohort"] == "excluded":
                status = "do_not_generate"
            elif not row["family"]:
                status = "operator_not_implemented"
            elif level["cohort"] == "edge_case" and not include_edge_cases:
                status = "edge_case_opt_in_required"
            else:
                status = "eligible"
            entries.append({
                "source_row": row["source_row"], "content_id": row["content_id"],
                "damage_id": row["damage_id"], "damage_type": row["damage_type"],
                "visual_class": row["visual_class"], "severity": severity,
                "family": row["family"], **level, "issues": issues, "status": status,
                "target_area_fraction_proxy": AREA_PROXIES[severity] if row["family"] else None,
                "semantic_severity_validated": False,
            })
    if content_id and not entries:
        raise ValueError(f"unknown_content_id:{content_id}")
    return {"matrix_sha256": fingerprint(matrix), "entries": entries,
            "counts": dict(Counter(e["status"] for e in entries)),
            "policy": "Qualitative severity is unvalidated; area fractions are experimental presets. No inferred decisions."}
