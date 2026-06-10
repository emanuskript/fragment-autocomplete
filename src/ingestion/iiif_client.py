"""Load IIIF manifests from local files or remote URLs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests


class ManifestLoadError(RuntimeError):
  """Raised when a IIIF manifest cannot be loaded or parsed."""


def load_manifest_file(path: str | Path) -> tuple[dict[str, Any], str]:
  """Load a local manifest JSON file and return it with a file URI identifier."""
  manifest_path = Path(path)
  if not manifest_path.exists():
    raise ManifestLoadError(f"Manifest file not found: {manifest_path}")

  try:
    return json.loads(manifest_path.read_text(encoding="utf-8")), manifest_path.resolve().as_uri()
  except json.JSONDecodeError as exc:
    raise ManifestLoadError(f"Invalid JSON in manifest file {manifest_path}: {exc}") from exc


def fetch_manifest_url(url: str, timeout_seconds: int = 30) -> tuple[dict[str, Any], str, dict[str, str | None]]:
  """Fetch a remote manifest and retain cache-relevant response headers."""
  try:
    response = requests.get(url, timeout=timeout_seconds, headers={"Accept": "application/json, application/ld+json"})
    response.raise_for_status()
  except requests.RequestException as exc:
    raise ManifestLoadError(f"Could not fetch manifest URL {url}: {exc}") from exc

  try:
    manifest = response.json()
  except json.JSONDecodeError as exc:
    raise ManifestLoadError(f"Invalid JSON from manifest URL {url}: {exc}") from exc

  fetch_headers = {
    "etag": response.headers.get("ETag"),
    "last_modified": response.headers.get("Last-Modified"),
  }
  return manifest, url, fetch_headers
