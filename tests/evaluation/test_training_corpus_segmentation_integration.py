from __future__ import annotations

from pathlib import Path

from PIL import Image

from scripts import run_segmentation_pilot as runner


def write_bytes(path: Path, payload: bytes) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_bytes(payload)


def test_corpus_run_identity_is_deterministic_and_content_addressed(tmp_path: Path, monkeypatch):
  monkeypatch.setattr(runner, "ROOT", tmp_path)
  model_path = tmp_path / "model.pt"
  write_bytes(model_path, b"model")
  write_bytes(tmp_path / "page-a.jpg", b"page-a")
  write_bytes(tmp_path / "page-b.jpg", b"page-b")
  payload = {
    "dataset_id": "corpus-v0",
    "pilot_run_id": "prepared-v0",
    "model_id": "emanuskript",
  }
  samples = [
    {
      "sample_id": "b",
      "db_image_asset_id": "asset-b",
      "db_canvas_id": "canvas-b",
      "manuscript_id": "manuscript-b",
      "dataset_split": "test",
      "local_path": "page-b.jpg",
    },
    {
      "sample_id": "a",
      "db_image_asset_id": "asset-a",
      "db_canvas_id": "canvas-a",
      "manuscript_id": "manuscript-a",
      "dataset_split": "train",
      "local_path": "page-a.jpg",
    },
  ]
  kwargs = {
    "device": "cpu",
    "conf": 0.25,
    "imgsz": 320,
    "software_versions": {"torch": "test", "ultralytics": "test"},
  }

  first = runner.build_run_identity(payload, samples, model_path, **kwargs)
  reordered = runner.build_run_identity(payload, list(reversed(samples)), model_path, **kwargs)
  assert first == reordered

  write_bytes(tmp_path / "page-a.jpg", b"changed-page-a")
  changed = runner.build_run_identity(payload, samples, model_path, **kwargs)
  assert changed["run_identity_sha256"] != first["run_identity_sha256"]


def test_cached_masks_require_matching_identity_dimensions_and_hash(tmp_path: Path, monkeypatch):
  monkeypatch.setattr(runner, "ROOT", tmp_path)
  mask_path = tmp_path / "outputs/mask.png"
  mask_path.parent.mkdir(parents=True)
  Image.new("L", (5, 4), 255).save(mask_path)
  payload = {
    "status": "success",
    "orig_shape": [4, 5],
    "segmentation_provenance": {"run_identity_sha256": "identity"},
    "detections": [
      {
        "mask_path": "outputs/mask.png",
        "mask_dimensions_px": [5, 4],
        "mask_sha256": runner.file_sha256(mask_path),
      }
    ],
  }

  assert runner.cached_mask_artifacts_complete(payload, "identity")
  assert not runner.cached_mask_artifacts_complete(payload, "different-identity")

  Image.new("L", (5, 4), 0).save(mask_path)
  assert not runner.cached_mask_artifacts_complete(payload, "identity")
