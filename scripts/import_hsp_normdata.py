#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingestion.db import connect


DEFAULT_TERMS = ROOT / "data/metadata/hsp_normdata_terms.yaml"
DEFAULT_RESULTS = ROOT / "data/metadata/hsp_normdata_import_results.yaml"
EXPECTED_COUNTS = {
  "SCRP": 116,
  "FORM": 92,
  "CODC": 73,
  "BNDG": 240,
  "HSP_SIMPLIFIED": 18,
}


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Import HSP/German normdata terms into PostgreSQL.")
  parser.add_argument("--terms", default=str(DEFAULT_TERMS))
  parser.add_argument("--output", default=str(DEFAULT_RESULTS))
  parser.add_argument("--dry-run", action="store_true")
  parser.add_argument("--verbose", action="store_true")
  return parser.parse_args()


def now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
  if not path.exists():
    raise FileNotFoundError(f"Missing normdata YAML: {path}")
  data = yaml.safe_load(path.read_text(encoding="utf-8"))
  if not isinstance(data, dict):
    raise ValueError(f"Expected mapping in {path}")
  return data


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def ensure_tables_exist(conn) -> None:
  with conn.cursor() as cur:
    cur.execute("SELECT to_regclass('public.controlled_vocabulary'), to_regclass('public.controlled_term')")
    row = cur.fetchone()
    if row[0] is None or row[1] is None:
      raise RuntimeError("controlled_vocabulary and controlled_term tables are missing. Run database migrations first.")


def upsert_vocabulary(cur, vocab: dict[str, Any], terms_path: Path) -> tuple[str, bool]:
  cur.execute(
    "SELECT id FROM controlled_vocabulary WHERE code = %s",
    (vocab["code"],),
  )
  existing = cur.fetchone()
  cur.execute(
    """
    INSERT INTO controlled_vocabulary (
      code, name, source_name, source_path, description, expected_term_count, raw_metadata
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
    ON CONFLICT (code) DO UPDATE
    SET name = EXCLUDED.name,
        source_name = EXCLUDED.source_name,
        source_path = EXCLUDED.source_path,
        description = EXCLUDED.description,
        expected_term_count = EXCLUDED.expected_term_count,
        raw_metadata = EXCLUDED.raw_metadata,
        updated_at = now()
    RETURNING id
    """,
    (
      vocab["code"],
      vocab["name"],
      vocab["source_sheet"],
      terms_path.relative_to(ROOT).as_posix(),
      f"Imported from {vocab['source_sheet']}",
      vocab.get("expected_term_count"),
      json.dumps(
        {
          "source_sheet": vocab.get("source_sheet"),
          "actual_term_count": vocab.get("actual_term_count"),
          "source_yaml": terms_path.relative_to(ROOT).as_posix(),
        }
      ),
    ),
  )
  row = cur.fetchone()
  return str(row[0]), existing is None


def upsert_term(cur, vocabulary_id: str, term: dict[str, Any]) -> bool:
  cur.execute(
    "SELECT id FROM controlled_term WHERE vocabulary_id = %s AND notation = %s",
    (vocabulary_id, term["notation"]),
  )
  existing = cur.fetchone()
  cur.execute(
    """
    INSERT INTO controlled_term (
      vocabulary_id, notation, label_de, label_en, code_group, norm_uuid,
      allowed_values, source_sheet, raw_metadata
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb)
    ON CONFLICT (vocabulary_id, notation) DO UPDATE
    SET label_de = EXCLUDED.label_de,
        label_en = EXCLUDED.label_en,
        code_group = EXCLUDED.code_group,
        norm_uuid = EXCLUDED.norm_uuid,
        allowed_values = EXCLUDED.allowed_values,
        source_sheet = EXCLUDED.source_sheet,
        raw_metadata = EXCLUDED.raw_metadata,
        updated_at = now()
    """,
    (
      vocabulary_id,
      term["notation"],
      term.get("label_de"),
      term.get("label_en"),
      term.get("code_group"),
      term.get("norm_uuid"),
      json.dumps(term.get("allowed_values", [])),
      term.get("source_sheet"),
      json.dumps({"source_row": term.get("source_row"), "raw": term.get("raw", {})}),
    ),
  )
  return existing is None


def count_terms(cur) -> dict[str, int]:
  cur.execute(
    """
    SELECT cv.code, count(ct.id)::int
    FROM controlled_vocabulary cv
    LEFT JOIN controlled_term ct ON ct.vocabulary_id = cv.id
    GROUP BY cv.code
    ORDER BY cv.code
    """
  )
  return {row[0]: row[1] for row in cur.fetchall()}


def validate_required_terms(cur) -> list[str]:
  checks = [
    ("SCRP", "SCRP-X710"),
    ("CODC", "CODC-A366"),
    ("HSP_SIMPLIFIED", "form"),
    ("HSP_SIMPLIFIED", "status"),
  ]
  failures: list[str] = []
  for vocab_code, notation in checks:
    cur.execute(
      """
      SELECT count(*)
      FROM controlled_term ct
      JOIN controlled_vocabulary cv ON cv.id = ct.vocabulary_id
      WHERE cv.code = %s AND ct.notation = %s
      """,
      (vocab_code, notation),
    )
    if cur.fetchone()[0] != 1:
      failures.append(f"Missing required term {vocab_code}:{notation}")
  return failures


def import_terms(payload: dict[str, Any], terms_path: Path, dry_run: bool) -> dict[str, Any]:
  results = {
    "generated_at": now_iso(),
    "status": "dry_run" if dry_run else "imported",
    "source_yaml": terms_path.relative_to(ROOT).as_posix(),
    "database_write": not dry_run,
    "vocabularies": [],
    "validation": {},
  }

  with connect() as conn:
    ensure_tables_exist(conn)
    with conn.cursor() as cur:
      for vocab in payload.get("vocabularies", []):
        expected = EXPECTED_COUNTS.get(vocab["code"], vocab.get("expected_term_count"))
        actual = len(vocab.get("terms", []))
        if dry_run:
          results["vocabularies"].append(
            {
              "code": vocab["code"],
              "expected_term_count": expected,
              "source_term_count": actual,
              "inserted_terms": 0,
              "updated_terms": 0,
              "status": "dry_run_ready",
            }
          )
          continue

        vocabulary_id, vocabulary_inserted = upsert_vocabulary(cur, vocab, terms_path)
        inserted_terms = 0
        updated_terms = 0
        seen: set[str] = set()
        for term in vocab.get("terms", []):
          notation = term["notation"]
          if notation in seen:
            raise RuntimeError(f"Duplicate notation in source YAML for {vocab['code']}: {notation}")
          seen.add(notation)
          if upsert_term(cur, vocabulary_id, term):
            inserted_terms += 1
          else:
            updated_terms += 1
        results["vocabularies"].append(
          {
            "code": vocab["code"],
            "vocabulary_id": vocabulary_id,
            "vocabulary_inserted": vocabulary_inserted,
            "expected_term_count": expected,
            "source_term_count": actual,
            "inserted_terms": inserted_terms,
            "updated_terms": updated_terms,
            "status": "imported",
          }
        )

      if dry_run:
        conn.rollback()
        results["validation"] = {"status": "not_run_in_dry_run"}
        return results

      db_counts = count_terms(cur)
      failures = []
      for code, expected in EXPECTED_COUNTS.items():
        actual = db_counts.get(code, 0)
        if actual != expected:
          failures.append(f"{code} expected {expected}, found {actual}")
      failures.extend(validate_required_terms(cur))
      results["validation"] = {
        "status": "passed" if not failures else "failed",
        "db_counts": db_counts,
        "failures": failures,
      }
      if failures:
        conn.rollback()
        raise RuntimeError("; ".join(failures))
      conn.commit()

  return results


def main() -> int:
  args = parse_args()
  terms_path = Path(args.terms).resolve()
  output_path = Path(args.output).resolve()
  payload = load_yaml(terms_path)
  results = import_terms(payload, terms_path, args.dry_run)
  write_yaml(output_path, results)
  if args.verbose:
    for vocab in results["vocabularies"]:
      print(
        f"{vocab['code']}: source={vocab['source_term_count']} "
        f"inserted={vocab['inserted_terms']} updated={vocab['updated_terms']}"
      )
    print(f"Validation: {results['validation'].get('status')}")
    print(f"Wrote {output_path.relative_to(ROOT)}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
