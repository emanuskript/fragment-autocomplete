"""Validate and register artificial-fragment task metadata without storing binaries."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from PIL import Image
import yaml


REGISTRATION_VERSION = "artificial_fragment_task_registration_v0_1"
IDENTITY_VERSION = "artificial_fragment_task_identity_v1"
EXPECTED_CORE_TASKS = 20
EXPECTED_SANITY_TASKS = 3
REQUIRED_ARTIFACTS = (
  "fragment_image",
  "observed_fragment_survival_mask",
  "source_survival_mask",
  "source_damage_mask",
)


def canonical_json(value: Any) -> str:
  """Serialize JSON deterministically for identity and equality checks."""
  return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_file(path: Path) -> str:
  digest = sha256()
  with path.open("rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
      digest.update(chunk)
  return digest.hexdigest()


def _mapping(value: Any, name: str) -> dict[str, Any]:
  if not isinstance(value, dict):
    raise ValueError(f"Required task metadata is incomplete: {name} must be an object")
  return value


def _list(value: Any, name: str) -> list[Any]:
  if not isinstance(value, list):
    raise ValueError(f"Required task metadata is incomplete: {name} must be a list")
  return value


def _required(task: dict[str, Any], name: str) -> Any:
  value = task.get(name)
  if value is None or value == "":
    raise ValueError(f"Required task metadata is incomplete: {name}")
  return value


def _uuid(value: Any, name: str) -> str:
  try:
    return str(UUID(str(value)))
  except (TypeError, ValueError) as exc:
    raise ValueError(f"Required task metadata has invalid {name}: {value}") from exc


def resolve_local_path(root: Path, recorded_path: str) -> Path:
  """Resolve a recorded project-relative path and reject path traversal."""
  path = Path(recorded_path)
  resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
  try:
    resolved.relative_to(root.resolve())
  except ValueError as exc:
    raise ValueError(f"Referenced path is outside the project root: {recorded_path}") from exc
  return resolved


def validate_artifact(root: Path, name: str, artifact: dict[str, Any]) -> None:
  recorded_path = _required(artifact, "path")
  expected_sha256 = _required(artifact, "sha256")
  path = resolve_local_path(root, str(recorded_path))
  if not path.is_file():
    raise FileNotFoundError(f"Referenced {name} artifact does not exist: {recorded_path}")
  actual_sha256 = sha256_file(path)
  if actual_sha256 != expected_sha256:
    raise ValueError(
      f"Checksum mismatch for {name} artifact {recorded_path}: "
      f"metadata={expected_sha256}, local={actual_sha256}"
    )
  dimensions = artifact.get("dimensions_px")
  if dimensions is not None:
    expected_size = tuple(int(value) for value in _list(dimensions, f"{name}.dimensions_px"))
    if len(expected_size) != 2:
      raise ValueError(f"Required task metadata is incomplete: {name}.dimensions_px")
    with Image.open(path) as image:
      if image.size != expected_size:
        raise ValueError(
          f"Dimension mismatch for {name} artifact {recorded_path}: "
          f"metadata={expected_size}, local={image.size}"
        )


def scientific_identity_payload(task: dict[str, Any]) -> dict[str, Any]:
  """Select generation parameters that define one scientific task configuration."""
  generator_parameters = _mapping(_required(task, "parameters"), "parameters")
  return {
    "identity_version": IDENTITY_VERSION,
    "source_sample_id": _required(task, "source_sample_id"),
    "source_sha256": _required(task, "source_sha256"),
    "generation_version": _required(task, "generation_version"),
    "mask_family": _required(task, "mask_family"),
    "random_seed": int(_required(task, "random_seed")),
    "requested_severity": float(_required(task, "requested_severity")),
    "rotation_degrees": float(_required(task, "rotation_degrees")),
    "scale": float(_required(task, "scale")),
    "mask_parameters": deepcopy(_mapping(_required(generator_parameters, "mask_parameters"), "parameters.mask_parameters")),
  }


def task_identity(task: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
  payload = scientific_identity_payload(task)
  identity_sha256 = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
  task_uuid = str(uuid5(NAMESPACE_URL, f"fragment-autocomplete/artificial-fragment-task/{identity_sha256}"))
  return task_uuid, identity_sha256, payload


def build_parameters(
  task: dict[str, Any],
  metadata_artifact: dict[str, Any],
  identity_sha256: str,
  identity_payload: dict[str, Any],
) -> dict[str, Any]:
  """Build the JSONB payload containing provenance and artifact references only."""
  artifacts = deepcopy(_mapping(task["artifacts"], "artifacts"))
  artifacts["metadata"] = deepcopy(metadata_artifact)
  crop_transform = _mapping(task["crop_transform"], "crop_transform")
  contour = _mapping(task["fragment_contour"], "fragment_contour")
  bbox = _mapping(task["fragment_bounding_box"], "fragment_bounding_box")
  layout = _mapping(task["layout_survival_estimate"], "layout_survival_estimate")
  return {
    "registration_version": REGISTRATION_VERSION,
    "task_identity": {
      "identity_version": IDENTITY_VERSION,
      "sha256": identity_sha256,
      "payload": deepcopy(identity_payload),
    },
    "task_id": task["task_id"],
    "task_group": task["task_group"],
    "generation_fingerprint_sha256": task["generation_fingerprint_sha256"],
    "source_sample_id": task["source_sample_id"],
    "source_path": task["source_path"],
    "source_sha256": task["source_sha256"],
    "source_dimensions_px": deepcopy(task["original_image_dimensions_px"]),
    "generated_fragment_dimensions_px": deepcopy(task["generated_fragment_dimensions_px"]),
    "requested_severity": task["requested_severity"],
    "measured_severity": task["measured_severity"],
    "surviving_fraction": task["surviving_fraction"],
    "rotation_degrees": task["rotation_degrees"],
    "scale": task["scale"],
    "source_sha256_after_generation": task["source_sha256_after_generation"],
    "source_integrity_verified": task["source_integrity_verified"],
    "artifacts": artifacts,
    "fragment_artifact": deepcopy(artifacts["fragment_image"]),
    "survival_mask_artifact": deepcopy(artifacts["source_survival_mask"]),
    "damage_mask_artifact": deepcopy(artifacts["source_damage_mask"]),
    "source_space_contour_xy_px": deepcopy(contour["source_page_xy_px"]),
    "source_space_bbox_xyxy_px": deepcopy(bbox["source_page_bbox_xyxy_px"]),
    "source_to_fragment_transform": deepcopy(crop_transform["source_to_observed_fragment_matrix"]),
    "fragment_to_source_transform": deepcopy(crop_transform["observed_fragment_to_source_matrix"]),
    "segmentation_run_provenance": deepcopy(layout["segmentation_run_provenance"]),
    "layout_geometry_method": layout["geometry_method"],
    "layout_survival_measurements": deepcopy(layout["regions"]),
    "layout_survival_summary": deepcopy(layout["summary"]),
    "generator_parameters": deepcopy(task["parameters"]),
    "mask_semantics": deepcopy(task["mask_semantics"]),
    "source_provenance": deepcopy(task["source_provenance"]),
    "scientific_roles": {
      "generated_fragment": "observed_evidence",
      "complete_source_page": "hidden_ground_truth",
      "contains_inferred_or_reconstructed_content": False,
    },
    "binary_data_stored_in_postgresql": False,
  }


@dataclass(frozen=True)
class TaskRegistrationRecord:
  task_id: str
  task_group: str
  database_id: str
  identity_sha256: str
  identity_payload: dict[str, Any]
  source_canvas_id: str
  source_image_asset_id: str
  source_path: str
  source_sha256: str
  source_dimensions_px: list[int]
  segmentation_run_id: str
  mask_path: str
  mask_family: str
  random_seed: int
  crop_transform: dict[str, Any]
  degradation_profile: dict[str, Any]
  ground_truth_placement: dict[str, Any]
  split_name: str
  generation_version: str
  parameters: dict[str, Any]

  def database_values(self) -> dict[str, Any]:
    return {
      "id": self.database_id,
      "source_canvas_id": self.source_canvas_id,
      "source_image_asset_id": self.source_image_asset_id,
      "generated_fragment_image_asset_id": None,
      "mask_path": self.mask_path,
      "mask_family": self.mask_family,
      "random_seed": self.random_seed,
      "crop_transform": deepcopy(self.crop_transform),
      "degradation_profile": deepcopy(self.degradation_profile),
      "ground_truth_placement": deepcopy(self.ground_truth_placement),
      "split_name": self.split_name,
      "generation_version": self.generation_version,
      "parameters": deepcopy(self.parameters),
    }


def _validate_full_task(root: Path, task: dict[str, Any], metadata_artifact: dict[str, Any]) -> TaskRegistrationRecord:
  required_mappings = (
    "artifacts",
    "crop_transform",
    "degradation_profile",
    "ground_truth_placement",
    "fragment_contour",
    "fragment_bounding_box",
    "layout_survival_estimate",
    "parameters",
    "mask_semantics",
    "source_provenance",
  )
  for name in required_mappings:
    _mapping(_required(task, name), name)
  for name in (
    "task_id",
    "task_group",
    "generation_version",
    "generation_fingerprint_sha256",
    "source_sample_id",
    "source_path",
    "source_sha256",
    "source_sha256_after_generation",
    "source_canvas_id",
    "source_image_asset_id",
    "mask_family",
    "random_seed",
    "requested_severity",
    "measured_severity",
    "surviving_fraction",
    "rotation_degrees",
    "scale",
    "split_name",
  ):
    _required(task, name)
  if task.get("source_integrity_verified") is not True:
    raise ValueError(f"Source integrity is not verified for {task.get('task_id')}")
  if task["source_sha256_after_generation"] != task["source_sha256"]:
    raise ValueError(f"Source checksum differs after generation for {task['task_id']}")

  source_canvas_id = _uuid(task["source_canvas_id"], "source_canvas_id")
  source_image_asset_id = _uuid(task["source_image_asset_id"], "source_image_asset_id")
  source_dimensions = [int(value) for value in _list(task.get("original_image_dimensions_px"), "original_image_dimensions_px")]
  generated_dimensions = [int(value) for value in _list(task.get("generated_fragment_dimensions_px"), "generated_fragment_dimensions_px")]
  if len(source_dimensions) != 2 or len(generated_dimensions) != 2:
    raise ValueError(f"Required task dimensions are incomplete for {task['task_id']}")

  source_path = resolve_local_path(root, str(task["source_path"]))
  if not source_path.is_file():
    raise FileNotFoundError(f"Source asset is missing for {task['task_id']}: {task['source_path']}")
  actual_source_sha256 = sha256_file(source_path)
  if actual_source_sha256 != task["source_sha256"]:
    raise ValueError(
      f"Source checksum differs for {task['task_id']}: "
      f"metadata={task['source_sha256']}, local={actual_source_sha256}"
    )
  with Image.open(source_path) as source_image:
    if source_image.size != tuple(source_dimensions):
      raise ValueError(f"Source dimensions differ for {task['task_id']}")

  artifacts = _mapping(task["artifacts"], "artifacts")
  for name in REQUIRED_ARTIFACTS:
    artifact = _mapping(_required(artifacts, name), f"artifacts.{name}")
    validate_artifact(root, name, artifact)
  validate_artifact(root, "metadata", metadata_artifact)

  ground_truth = _mapping(task["ground_truth_placement"], "ground_truth_placement")
  if _uuid(ground_truth.get("source_canvas_id"), "ground_truth.source_canvas_id") != source_canvas_id:
    raise ValueError(f"Ground-truth canvas ID mismatch for {task['task_id']}")
  if _uuid(ground_truth.get("source_image_asset_id"), "ground_truth.source_image_asset_id") != source_image_asset_id:
    raise ValueError(f"Ground-truth image asset ID mismatch for {task['task_id']}")
  if ground_truth.get("placement_is_known") is not True:
    raise ValueError(f"Ground-truth placement is incomplete for {task['task_id']}")

  layout = _mapping(task["layout_survival_estimate"], "layout_survival_estimate")
  provenance = _mapping(_required(layout, "segmentation_run_provenance"), "segmentation_run_provenance")
  segmentation_run_id = _uuid(provenance.get("db_segmentation_run_id"), "db_segmentation_run_id")
  _list(_required(layout, "regions"), "layout_survival_estimate.regions")
  _mapping(_required(layout, "summary"), "layout_survival_estimate.summary")
  _required(layout, "geometry_method")

  database_id, identity_sha256, identity_payload = task_identity(task)
  parameters = build_parameters(task, metadata_artifact, identity_sha256, identity_payload)
  return TaskRegistrationRecord(
    task_id=str(task["task_id"]),
    task_group=str(task["task_group"]),
    database_id=database_id,
    identity_sha256=identity_sha256,
    identity_payload=identity_payload,
    source_canvas_id=source_canvas_id,
    source_image_asset_id=source_image_asset_id,
    source_path=str(task["source_path"]),
    source_sha256=str(task["source_sha256"]),
    source_dimensions_px=source_dimensions,
    segmentation_run_id=segmentation_run_id,
    mask_path=str(artifacts["source_survival_mask"]["path"]),
    mask_family=str(task["mask_family"]),
    random_seed=int(task["random_seed"]),
    crop_transform=deepcopy(task["crop_transform"]),
    degradation_profile=deepcopy(task["degradation_profile"]),
    ground_truth_placement=deepcopy(ground_truth),
    split_name=str(task["split_name"]),
    generation_version=str(task["generation_version"]),
    parameters=parameters,
  )


def load_registration_records(
  manifest_path: Path,
  root: Path,
  *,
  expected_core_tasks: int = EXPECTED_CORE_TASKS,
  expected_sanity_tasks: int = EXPECTED_SANITY_TASKS,
) -> list[TaskRegistrationRecord]:
  """Load the controlled 23-task pilot and validate all referenced local evidence."""
  if not manifest_path.is_file():
    raise FileNotFoundError(f"Artificial-fragment manifest is missing: {manifest_path}")
  manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
  if not isinstance(manifest, dict):
    raise ValueError(f"Expected mapping in {manifest_path}")
  core = _list(manifest.get("core_pilot_tasks"), "core_pilot_tasks")
  sanity = _list(manifest.get("transformation_sanity_tasks"), "transformation_sanity_tasks")
  if len(core) != expected_core_tasks or len(sanity) != expected_sanity_tasks:
    raise ValueError(
      f"Expected {expected_core_tasks} core and {expected_sanity_tasks} sanity tasks; "
      f"found {len(core)} and {len(sanity)}"
    )
  if manifest.get("generated_task_count") != expected_core_tasks + expected_sanity_tasks:
    raise ValueError("Generated task count is incomplete")

  records: list[TaskRegistrationRecord] = []
  seen_identities: dict[str, str] = {}
  for expected_group, index_task in [("core_pilot", item) for item in core] + [
    ("transformation_sanity", item) for item in sanity
  ]:
    index_task = _mapping(index_task, "task index record")
    metadata_artifact = _mapping(
      _required(_mapping(_required(index_task, "artifacts"), "artifacts"), "metadata"),
      "artifacts.metadata",
    )
    validate_artifact(root, "metadata", metadata_artifact)
    metadata_path = resolve_local_path(root, str(metadata_artifact["path"]))
    task = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(task, dict):
      raise ValueError(f"Expected task object in {metadata_path}")
    for name in (
      "task_id",
      "task_group",
      "generation_version",
      "generation_fingerprint_sha256",
      "source_canvas_id",
      "source_image_asset_id",
      "source_sha256",
    ):
      if task.get(name) != index_task.get(name):
        raise ValueError(f"Manifest/per-task metadata mismatch for {name}: {metadata_path}")
    if task.get("task_group") != expected_group:
      raise ValueError(f"Unexpected task group for {task.get('task_id')}: {task.get('task_group')}")
    if expected_group == "core_pilot" and task.get("layout_survival_estimate", {}).get("geometry_method") != "segmentation_mask":
      raise ValueError(f"Core task does not use segmentation_mask survival data: {task.get('task_id')}")
    record = _validate_full_task(root, task, metadata_artifact)
    duplicate = seen_identities.get(record.identity_sha256)
    if duplicate:
      raise ValueError(
        f"Duplicate scientific task configuration: {duplicate} and {record.task_id} "
        f"share identity {record.identity_sha256}"
      )
    seen_identities[record.identity_sha256] = record.task_id
    records.append(record)
  return records


@dataclass(frozen=True)
class SourceDatabaseContext:
  image_asset_id: str
  canvas_id: str | None
  local_path: str | None
  checksum_sha256: str | None
  width_px: int | None
  height_px: int | None


class ArtificialFragmentTaskStore(Protocol):
  def source_context(self, image_asset_id: str) -> SourceDatabaseContext | None: ...

  def segmentation_run_image_asset_id(self, segmentation_run_id: str) -> str | None: ...

  def upsert_task(self, record: TaskRegistrationRecord) -> str: ...


def validate_source_relationship(store: ArtificialFragmentTaskStore, record: TaskRegistrationRecord) -> None:
  context = store.source_context(record.source_image_asset_id)
  if context is None:
    raise ValueError(
      f"Source image_asset is missing for {record.task_id}: {record.source_image_asset_id}"
    )
  if context.canvas_id != record.source_canvas_id:
    raise ValueError(
      f"Source canvas relationship differs for {record.task_id}: "
      f"metadata={record.source_canvas_id}, database={context.canvas_id}"
    )
  if context.local_path != record.source_path:
    raise ValueError(
      f"Source asset path differs for {record.task_id}: "
      f"metadata={record.source_path}, database={context.local_path}"
    )
  if context.checksum_sha256 and context.checksum_sha256 != record.source_sha256:
    raise ValueError(
      f"Source database checksum differs for {record.task_id}: "
      f"metadata={record.source_sha256}, database={context.checksum_sha256}"
    )
  expected_dimensions = tuple(record.source_dimensions_px)
  stored_dimensions = (context.width_px, context.height_px)
  if all(value is not None for value in stored_dimensions) and stored_dimensions != expected_dimensions:
    raise ValueError(
      f"Source database dimensions differ for {record.task_id}: "
      f"metadata={expected_dimensions}, database={stored_dimensions}"
    )
  run_image_asset_id = store.segmentation_run_image_asset_id(record.segmentation_run_id)
  if run_image_asset_id is None:
    raise ValueError(
      f"Referenced segmentation_run is missing for {record.task_id}: {record.segmentation_run_id}"
    )
  if run_image_asset_id != record.source_image_asset_id:
    raise ValueError(
      f"Segmentation-run source differs for {record.task_id}: "
      f"task={record.source_image_asset_id}, run={run_image_asset_id}"
    )


def register_records(
  store: ArtificialFragmentTaskStore,
  records: list[TaskRegistrationRecord],
  *,
  dry_run: bool = False,
) -> dict[str, int]:
  """Validate relationships and insert, update, or match every deterministic task."""
  stats = {"inserted": 0, "updated": 0, "matched": 0, "validated": 0}
  for record in records:
    validate_source_relationship(store, record)
    stats["validated"] += 1
    if dry_run:
      continue
    action = store.upsert_task(record)
    if action not in {"inserted", "updated", "matched"}:
      raise RuntimeError(f"Unexpected registration action: {action}")
    stats[action] += 1
  return stats
