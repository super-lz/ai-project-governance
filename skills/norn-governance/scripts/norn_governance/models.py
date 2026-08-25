from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping


PLAN_SCHEMA_VERSION = 1
MANIFEST_SCHEMA_VERSION = 1


class ProjectState(str, Enum):
    UNINITIALIZED = "uninitialized"
    CURRENT = "current"
    UPGRADEABLE = "upgradeable"
    LEGACY = "legacy"
    MIXED = "mixed"
    AMBIGUOUS = "ambiguous"
    CONFLICT = "conflict"


class ActionKind(str, Enum):
    CREATE = "create"
    MOVE = "move"
    MERGE = "merge"
    DELETE = "delete"
    KEEP = "keep"
    CONFLICT = "conflict"


class PathKind(str, Enum):
    MISSING = "missing"
    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    OTHER = "other"


class OwnershipKind(str, Enum):
    MANAGED = "managed"
    MIXED = "mixed"
    PROJECT = "project"


class ConflictChoice(str, Enum):
    KEEP_CURRENT = "keep-current"
    ADOPT_TEMPLATE = "adopt-template"
    SEMANTIC_MERGE = "semantic-merge"


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_sha256(value: str | None, field_name: str, *, optional: bool) -> None:
    if value is None and optional:
        return
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{field_name} must be a SHA-256 hex digest")
    try:
        bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a SHA-256 hex digest") from exc


def _require_nonnegative_integer(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a nonnegative integer")


def _require_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _parse_enum(enum_type: type[Enum], value: object, field_name: str) -> Enum:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field_name}: {value!r}") from exc


@dataclass(frozen=True)
class PathFingerprint:
    exists: bool
    kind: PathKind
    sha256: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PathKind):
            object.__setattr__(self, "kind", _parse_enum(PathKind, self.kind, "path kind"))
        if self.kind is PathKind.MISSING:
            if self.exists or self.sha256 is not None:
                raise ValueError("missing fingerprint must not exist or have SHA-256")
            return
        if not self.exists:
            raise ValueError("existing path kind requires exists=true")
        if self.kind in {PathKind.FILE, PathKind.DIRECTORY}:
            _require_sha256(self.sha256, "sha256", optional=False)
        elif self.sha256 is not None:
            raise ValueError("unsupported path kinds must not have SHA-256")

    @classmethod
    def missing(cls) -> PathFingerprint:
        return cls(False, PathKind.MISSING, None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "exists": self.exists,
            "kind": self.kind.value,
            "sha256": self.sha256,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> PathFingerprint:
        return cls(
            exists=payload.get("exists"),
            kind=_parse_enum(PathKind, payload.get("kind"), "path kind"),
            sha256=payload.get("sha256"),
        )


@dataclass(frozen=True)
class PlannedAction:
    action_id: str
    kind: ActionKind
    source_path: str | None
    target_path: str
    source_before: PathFingerprint | None
    target_before: PathFingerprint
    output_sha256: str | None
    ownership: OwnershipKind
    evidence: tuple[str, ...]
    reason: str
    risk: str
    verification: tuple[str, ...]
    allowed_resolutions: tuple[ConflictChoice, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ActionKind):
            object.__setattr__(self, "kind", _parse_enum(ActionKind, self.kind, "action kind"))
        if not isinstance(self.ownership, OwnershipKind):
            object.__setattr__(
                self,
                "ownership",
                _parse_enum(OwnershipKind, self.ownership, "ownership"),
            )
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "verification", tuple(self.verification))
        object.__setattr__(
            self,
            "allowed_resolutions",
            tuple(
                choice
                if isinstance(choice, ConflictChoice)
                else _parse_enum(ConflictChoice, choice, "conflict choice")
                for choice in self.allowed_resolutions
            ),
        )
        if not self.action_id or not isinstance(self.action_id, str):
            raise ValueError("action_id must be a nonempty string")
        if not self.target_path or not isinstance(self.target_path, str):
            raise ValueError("target_path must be a nonempty string")
        if self.source_path is not None and self.source_before is None:
            raise ValueError("source_before is required when source_path is set")
        if self.source_path is None and self.source_before is not None:
            raise ValueError("source_before requires source_path")
        if not isinstance(self.target_before, PathFingerprint):
            raise ValueError("target_before must be a PathFingerprint")
        if self.kind in {ActionKind.CREATE, ActionKind.MOVE, ActionKind.MERGE}:
            _require_sha256(self.output_sha256, "output_sha256", optional=False)
        elif self.output_sha256 is not None:
            raise ValueError(f"{self.kind.value} action must not have output_sha256")
        if self.kind is not ActionKind.CONFLICT and self.allowed_resolutions:
            raise ValueError("allowed_resolutions require conflict action")
        if len(set(self.allowed_resolutions)) != len(self.allowed_resolutions):
            raise ValueError("allowed_resolutions must be unique")
        for field_name, values in (
            ("evidence", self.evidence),
            ("verification", self.verification),
        ):
            if not all(isinstance(value, str) and value for value in values):
                raise ValueError(f"{field_name} must contain nonempty strings")
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("reason must be a nonempty string")
        if not isinstance(self.risk, str) or not self.risk:
            raise ValueError("risk must be a nonempty string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "kind": self.kind.value,
            "source_path": self.source_path,
            "target_path": self.target_path,
            "source_before": (
                self.source_before.to_dict() if self.source_before is not None else None
            ),
            "target_before": self.target_before.to_dict(),
            "output_sha256": self.output_sha256,
            "ownership": self.ownership.value,
            "evidence": list(self.evidence),
            "reason": self.reason,
            "risk": self.risk,
            "verification": list(self.verification),
            "allowed_resolutions": [choice.value for choice in self.allowed_resolutions],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> PlannedAction:
        source_before = payload.get("source_before")
        target_before = _require_mapping(payload.get("target_before"), "target_before")
        return cls(
            action_id=payload.get("action_id"),
            kind=_parse_enum(ActionKind, payload.get("kind"), "action kind"),
            source_path=payload.get("source_path"),
            target_path=payload.get("target_path"),
            source_before=(
                PathFingerprint.from_dict(
                    _require_mapping(source_before, "source_before")
                )
                if source_before is not None
                else None
            ),
            target_before=PathFingerprint.from_dict(target_before),
            output_sha256=payload.get("output_sha256"),
            ownership=_parse_enum(
                OwnershipKind, payload.get("ownership"), "ownership"
            ),
            evidence=tuple(payload.get("evidence", ())),
            reason=payload.get("reason"),
            risk=payload.get("risk"),
            verification=tuple(payload.get("verification", ())),
            allowed_resolutions=tuple(
                _parse_enum(ConflictChoice, value, "conflict choice")
                for value in payload.get("allowed_resolutions", ())
            ),
        )


@dataclass(frozen=True)
class GovernancePlan:
    plan_schema_version: int
    target_root: str
    project_state: ProjectState
    template_version: int
    actions: tuple[PlannedAction, ...]
    conflicts: tuple[str, ...]
    plan_sha256: str

    def __post_init__(self) -> None:
        if self.plan_schema_version != PLAN_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported plan schema: {self.plan_schema_version}"
            )
        if not isinstance(self.project_state, ProjectState):
            object.__setattr__(
                self,
                "project_state",
                _parse_enum(ProjectState, self.project_state, "project state"),
            )
        _require_nonnegative_integer(self.template_version, "template_version")
        object.__setattr__(self, "actions", tuple(self.actions))
        object.__setattr__(self, "conflicts", tuple(self.conflicts))
        if not isinstance(self.target_root, str) or not Path(self.target_root).is_absolute():
            raise ValueError("target_root must be an absolute path")
        if not all(isinstance(action, PlannedAction) for action in self.actions):
            raise ValueError("actions must contain PlannedAction values")
        action_ids = [action.action_id for action in self.actions]
        if len(set(action_ids)) != len(action_ids):
            raise ValueError("action_id values must be unique")
        if not all(isinstance(item, str) and item for item in self.conflicts):
            raise ValueError("conflicts must contain nonempty strings")
        _require_sha256(self.plan_sha256, "plan_sha256", optional=False)

    @classmethod
    def build(
        cls,
        *,
        target_root: str,
        project_state: ProjectState,
        template_version: int,
        actions: Iterable[PlannedAction],
        conflicts: Iterable[str],
    ) -> GovernancePlan:
        actions_tuple = tuple(actions)
        conflicts_tuple = tuple(conflicts)
        payload = cls._payload_without_digest(
            target_root=target_root,
            project_state=project_state,
            template_version=template_version,
            actions=actions_tuple,
            conflicts=conflicts_tuple,
        )
        return cls(
            plan_schema_version=PLAN_SCHEMA_VERSION,
            target_root=target_root,
            project_state=project_state,
            template_version=template_version,
            actions=actions_tuple,
            conflicts=conflicts_tuple,
            plan_sha256=sha256_bytes(canonical_json_bytes(payload)),
        )

    @staticmethod
    def _payload_without_digest(
        *,
        target_root: str,
        project_state: ProjectState,
        template_version: int,
        actions: tuple[PlannedAction, ...],
        conflicts: tuple[str, ...],
    ) -> dict[str, Any]:
        state = (
            project_state.value
            if isinstance(project_state, ProjectState)
            else ProjectState(project_state).value
        )
        return {
            "plan_schema_version": PLAN_SCHEMA_VERSION,
            "target_root": target_root,
            "project_state": state,
            "template_version": template_version,
            "actions": [action.to_dict() for action in actions],
            "conflicts": list(conflicts),
        }

    def expected_digest(self) -> str:
        payload = self._payload_without_digest(
            target_root=self.target_root,
            project_state=self.project_state,
            template_version=self.template_version,
            actions=self.actions,
            conflicts=self.conflicts,
        )
        return sha256_bytes(canonical_json_bytes(payload))

    def to_dict(self) -> dict[str, Any]:
        payload = self._payload_without_digest(
            target_root=self.target_root,
            project_state=self.project_state,
            template_version=self.template_version,
            actions=self.actions,
            conflicts=self.conflicts,
        )
        payload["plan_sha256"] = self.plan_sha256
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> GovernancePlan:
        actions_payload = payload.get("actions")
        if not isinstance(actions_payload, list):
            raise ValueError("actions must be an array")
        conflicts_payload = payload.get("conflicts")
        if not isinstance(conflicts_payload, list):
            raise ValueError("conflicts must be an array")
        plan = cls(
            plan_schema_version=payload.get("plan_schema_version"),
            target_root=payload.get("target_root"),
            project_state=_parse_enum(
                ProjectState, payload.get("project_state"), "project state"
            ),
            template_version=payload.get("template_version"),
            actions=tuple(
                PlannedAction.from_dict(_require_mapping(item, "action"))
                for item in actions_payload
            ),
            conflicts=tuple(conflicts_payload),
            plan_sha256=payload.get("plan_sha256"),
        )
        if plan.plan_sha256 != plan.expected_digest():
            raise ValueError("plan digest mismatch")
        return plan


@dataclass(frozen=True)
class ManagedFileRecord:
    ownership: OwnershipKind
    base_sha256: str | None
    managed_blocks: tuple[str, ...]
    template_version: int

    def __post_init__(self) -> None:
        if not isinstance(self.ownership, OwnershipKind):
            object.__setattr__(
                self,
                "ownership",
                _parse_enum(OwnershipKind, self.ownership, "ownership"),
            )
        object.__setattr__(self, "managed_blocks", tuple(self.managed_blocks))
        _require_nonnegative_integer(self.template_version, "template_version")
        if len(set(self.managed_blocks)) != len(self.managed_blocks):
            raise ValueError("managed_blocks must be unique")
        if not all(
            isinstance(block_id, str) and block_id for block_id in self.managed_blocks
        ):
            raise ValueError("managed_blocks must contain nonempty strings")
        if self.ownership is OwnershipKind.PROJECT:
            if self.base_sha256 is not None or self.managed_blocks:
                raise ValueError(
                    "project-owned records must not define base_sha256 or managed_blocks"
                )
        else:
            _require_sha256(self.base_sha256, "base_sha256", optional=False)
            if not self.managed_blocks:
                raise ValueError("managed_blocks are required for managed ownership")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ownership": self.ownership.value,
            "base_sha256": self.base_sha256,
            "managed_blocks": list(self.managed_blocks),
            "template_version": self.template_version,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ManagedFileRecord:
        return cls(
            ownership=_parse_enum(
                OwnershipKind, payload.get("ownership"), "ownership"
            ),
            base_sha256=payload.get("base_sha256"),
            managed_blocks=tuple(payload.get("managed_blocks", ())),
            template_version=payload.get("template_version"),
        )


@dataclass(frozen=True)
class NornManifest:
    schema_version: int
    template_version: int
    managed_files: Mapping[str, ManagedFileRecord]

    def __post_init__(self) -> None:
        if self.schema_version != MANIFEST_SCHEMA_VERSION:
            raise ValueError(f"unsupported manifest schema: {self.schema_version}")
        _require_nonnegative_integer(self.template_version, "template_version")
        normalized: dict[str, ManagedFileRecord] = {}
        for path, record in sorted(self.managed_files.items()):
            if not isinstance(path, str) or not path:
                raise ValueError("managed file path must be a nonempty string")
            if not isinstance(record, ManagedFileRecord):
                raise ValueError("managed_files values must be ManagedFileRecord")
            normalized[path] = record
        object.__setattr__(self, "managed_files", MappingProxyType(normalized))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "template_version": self.template_version,
            "managed_files": {
                path: record.to_dict() for path, record in self.managed_files.items()
            },
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> NornManifest:
        managed_files = _require_mapping(payload.get("managed_files"), "managed_files")
        return cls(
            schema_version=payload.get("schema_version"),
            template_version=payload.get("template_version"),
            managed_files={
                path: ManagedFileRecord.from_dict(
                    _require_mapping(record, f"managed_files[{path!r}]")
                )
                for path, record in managed_files.items()
            },
        )


def write_plan(plan: GovernancePlan, directory: Path) -> Path:
    if plan.plan_sha256 != plan.expected_digest():
        raise ValueError("plan digest mismatch")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    plan_path = directory / "plan.json"
    payload = json.dumps(
        plan.to_dict(), ensure_ascii=False, sort_keys=True, indent=2
    ).encode("utf-8") + b"\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".plan.", suffix=".tmp", dir=directory
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, plan_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return plan_path


def load_plan(path: Path) -> GovernancePlan:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid plan file: {exc}") from exc
    return GovernancePlan.from_dict(_require_mapping(payload, "plan"))
