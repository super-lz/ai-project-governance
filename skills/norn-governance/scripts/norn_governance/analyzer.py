from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterable

from .managed_markdown import ManagedBlockError, parse_managed_blocks
from .models import (
    ActionKind,
    ConflictChoice,
    ConflictResolution,
    GovernancePlan,
    ManagedFileRecord,
    NornManifest,
    OwnershipKind,
    PathFingerprint,
    PathKind,
    PlannedAction,
    ProjectState,
    canonical_json_bytes,
    sha256_bytes,
    write_plan,
)
from .templates import (
    INITIALIZED_PATHS,
    MANAGED_PATHS,
    MANIFEST_PATH,
    TEMPLATE_VERSION,
    asset_template_root,
    legacy_template_root,
    load_manifest,
    manifest_bytes,
)
from .managed_markdown import replace_managed_block


LEGACY_PATH_MAP = {
    "docs/AGENTS.md": "norn-governance/AGENTS.md",
    "docs/spec/AGENTS.md": "norn-governance/spec/AGENTS.md",
    "docs/spec/main-spec.md": "norn-governance/spec/main-spec.md",
    "docs/appendix/README.md": "norn-governance/appendix/README.md",
}
GOVERNANCE_REFERENCE_MAP = {
    "docs/AGENTS.md": "norn-governance/AGENTS.md",
    "docs/spec/AGENTS.md": "norn-governance/spec/AGENTS.md",
    "docs/spec/main-spec.md": "norn-governance/spec/main-spec.md",
    "docs/appendix/README.md": "norn-governance/appendix/README.md",
}
ROOT_AGENTS = "AGENTS.md"
GOVERNANCE_DIRECTORY_PATHS = {
    "norn-governance",
    "norn-governance/spec",
    "norn-governance/appendix",
    "docs",
    "docs/spec",
    "docs/appendix",
}


def fingerprint_path(path: Path) -> PathFingerprint:
    path = Path(path)
    if path.is_symlink():
        return PathFingerprint(True, PathKind.SYMLINK, None)
    if not path.exists():
        return PathFingerprint.missing()
    if path.is_file():
        return PathFingerprint(True, PathKind.FILE, sha256_bytes(path.read_bytes()))
    if path.is_dir():
        entries = []
        for child in sorted(path.iterdir(), key=lambda item: item.name):
            if child.is_symlink():
                kind = PathKind.SYMLINK
            elif child.is_file():
                kind = PathKind.FILE
            elif child.is_dir():
                kind = PathKind.DIRECTORY
            else:
                kind = PathKind.OTHER
            entries.append({"name": child.name, "kind": kind.value})
        digest = sha256_bytes(canonical_json_bytes({"entries": entries}))
        return PathFingerprint(True, PathKind.DIRECTORY, digest)
    return PathFingerprint(True, PathKind.OTHER, None)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _same_bytes(first: Path, second: Path) -> bool:
    return first.is_file() and second.is_file() and first.read_bytes() == second.read_bytes()


def _is_exact_legacy(target_root: Path, relative_path: str) -> bool:
    return _same_bytes(
        target_root / relative_path,
        legacy_template_root() / relative_path,
    )


def _has_structural_legacy_evidence(target_root: Path) -> bool:
    root = _read_text(target_root / ROOT_AGENTS)
    docs = _read_text(target_root / "docs/AGENTS.md")
    spec = _read_text(target_root / "docs/spec/AGENTS.md")
    if root is None or docs is None or spec is None:
        return False
    root_links = "docs/AGENTS.md" in root and "docs/spec/main-spec.md" in root
    docs_roles = "spec/" in docs and "appendix/" in docs
    spec_authority = "main-spec.md" in spec and any(
        term in spec for term in ("权威", "主要依据", "实现依据")
    )
    return root_links and docs_roles and spec_authority


def _manifest_state(target_root: Path) -> ProjectState:
    manifest_path = target_root / MANIFEST_PATH
    try:
        manifest = load_manifest(manifest_path)
    except ValueError:
        return ProjectState.CONFLICT
    if manifest.template_version > TEMPLATE_VERSION:
        return ProjectState.CONFLICT
    if set(manifest.managed_files) != set(MANAGED_PATHS):
        return ProjectState.CONFLICT
    for relative_path, (ownership, expected_blocks) in MANAGED_PATHS.items():
        path = target_root / relative_path
        fingerprint = fingerprint_path(path)
        if fingerprint.kind is not PathKind.FILE:
            return ProjectState.MIXED
        record = manifest.managed_files[relative_path]
        if (
            record.ownership is not ownership
            or record.managed_blocks != expected_blocks
            or record.template_version != manifest.template_version
        ):
            return ProjectState.CONFLICT
        if ownership is OwnershipKind.PROJECT:
            continue
        text = _read_text(path)
        if text is None:
            return ProjectState.CONFLICT
        try:
            blocks = parse_managed_blocks(text)
        except ManagedBlockError:
            return ProjectState.CONFLICT
        if tuple(blocks) != expected_blocks:
            return ProjectState.CONFLICT
        if blocks[expected_blocks[0]].sha256 != record.base_sha256:
            if manifest.template_version >= TEMPLATE_VERSION:
                return ProjectState.CONFLICT
    if manifest.template_version < TEMPLATE_VERSION:
        return ProjectState.UPGRADEABLE
    return ProjectState.CURRENT


def classify_project(target_root: Path) -> ProjectState:
    target_root = Path(target_root).resolve()
    if not target_root.is_dir():
        return ProjectState.CONFLICT

    for relative_path in GOVERNANCE_DIRECTORY_PATHS:
        fingerprint = fingerprint_path(target_root / relative_path)
        if fingerprint.exists and fingerprint.kind is not PathKind.DIRECTORY:
            return ProjectState.CONFLICT

    inspected_file_paths = {
        ROOT_AGENTS,
        MANIFEST_PATH,
        *MANAGED_PATHS,
        *LEGACY_PATH_MAP,
    }
    for relative_path in inspected_file_paths:
        fingerprint = fingerprint_path(target_root / relative_path)
        if fingerprint.exists and fingerprint.kind is not PathKind.FILE:
            return ProjectState.CONFLICT

    legacy_existing = {
        path for path in LEGACY_PATH_MAP if (target_root / path).exists()
    }
    norn_existing = any(
        (target_root / path).exists()
        for path in (*MANAGED_PATHS.keys(), MANIFEST_PATH)
        if path != ROOT_AGENTS
    )
    manifest_exists = (target_root / MANIFEST_PATH).exists()

    if manifest_exists:
        manifest_state = _manifest_state(target_root)
        if manifest_state is ProjectState.CONFLICT:
            return manifest_state
        if legacy_existing:
            return ProjectState.MIXED
        return manifest_state

    if norn_existing:
        return ProjectState.MIXED

    if legacy_existing:
        exact = {path for path in legacy_existing if _is_exact_legacy(target_root, path)}
        complete = legacy_existing == set(LEGACY_PATH_MAP)
        root_path = target_root / ROOT_AGENTS
        root_exact = _is_exact_legacy(target_root, ROOT_AGENTS)
        root_current = _same_bytes(root_path, asset_template_root() / ROOT_AGENTS)
        if complete and exact == set(LEGACY_PATH_MAP):
            if not root_path.exists() or root_exact:
                return ProjectState.LEGACY
            if root_current:
                return ProjectState.MIXED
            return ProjectState.CONFLICT
        if complete and _has_structural_legacy_evidence(target_root):
            governance_paths = {
                "docs/AGENTS.md",
                "docs/spec/AGENTS.md",
                "docs/appendix/README.md",
            }
            if not root_current:
                governance_paths.add(ROOT_AGENTS)
            if all(
                not (target_root / path).exists() or _is_exact_legacy(target_root, path)
                for path in governance_paths
            ):
                return ProjectState.MIXED if root_current else ProjectState.LEGACY
            return ProjectState.CONFLICT
        if exact:
            return ProjectState.MIXED
        return ProjectState.AMBIGUOUS

    root = target_root / ROOT_AGENTS
    if root.exists():
        if _is_exact_legacy(target_root, ROOT_AGENTS):
            return ProjectState.MIXED
        return ProjectState.CONFLICT
    return ProjectState.UNINITIALIZED


def _ownership_for(relative_path: str) -> OwnershipKind:
    if relative_path == MANIFEST_PATH:
        return OwnershipKind.MANAGED
    if relative_path in MANAGED_PATHS:
        return MANAGED_PATHS[relative_path][0]
    if relative_path.endswith("main-spec.md"):
        return OwnershipKind.PROJECT
    return OwnershipKind.MANAGED


def _write_artifact(artifact_root: Path, action_id: str, body: bytes) -> str:
    rendered_root = artifact_root / "rendered"
    rendered_root.mkdir(parents=True, exist_ok=True)
    target = rendered_root / f"{action_id}.content"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{action_id}.", suffix=".tmp", dir=rendered_root
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, target)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return sha256_bytes(body)


def _action_id(prefix: str, relative_path: str) -> str:
    normalized = relative_path.replace("/", "-").replace(".", "-")
    return f"{prefix}-{normalized}".strip("-")


def _keep_action(
    target_root: Path,
    relative_path: str,
    *,
    reason: str,
) -> PlannedAction:
    return PlannedAction(
        action_id=_action_id("keep", relative_path),
        kind=ActionKind.KEEP,
        source_path=None,
        target_path=relative_path,
        source_before=None,
        target_before=fingerprint_path(target_root / relative_path),
        output_sha256=None,
        ownership=_ownership_for(relative_path),
        evidence=("canonical target already has the planned bytes",),
        reason=reason,
        risk="no file mutation",
        verification=("target fingerprint remains unchanged",),
        allowed_resolutions=(),
    )


def _conflict_action(
    target_root: Path,
    target_path: str,
    *,
    source_path: str | None = None,
    reason: str,
    evidence: Iterable[str],
    allowed_resolutions: tuple[ConflictChoice, ...] = (),
) -> PlannedAction:
    return PlannedAction(
        action_id=_action_id("conflict", target_path),
        kind=ActionKind.CONFLICT,
        source_path=source_path,
        target_path=target_path,
        source_before=(
            fingerprint_path(target_root / source_path) if source_path else None
        ),
        target_before=fingerprint_path(target_root / target_path),
        output_sha256=None,
        ownership=_ownership_for(target_path),
        evidence=tuple(evidence),
        reason=reason,
        risk="automatic execution is blocked until the conflict is resolved",
        verification=("fresh analysis contains no unresolved conflict action",),
        allowed_resolutions=allowed_resolutions,
    )


def _delete_action(
    target_root: Path,
    relative_path: str,
    *,
    reason: str,
) -> PlannedAction:
    return PlannedAction(
        action_id=_action_id("delete", relative_path),
        kind=ActionKind.DELETE,
        source_path=None,
        target_path=relative_path,
        source_before=None,
        target_before=fingerprint_path(target_root / relative_path),
        output_sha256=None,
        ownership=_ownership_for(relative_path),
        evidence=("canonical replacement is already verified by the plan",),
        reason=reason,
        risk="removes only the fingerprinted legacy duplicate or empty directory",
        verification=("path is absent after apply",),
        allowed_resolutions=(),
    )


def _plan_output(
    target_root: Path,
    artifact_root: Path,
    *,
    target_path: str,
    body: bytes,
    reason: str,
    evidence: Iterable[str],
    source_path: str | None = None,
    allow_existing_replace: bool = False,
) -> list[PlannedAction]:
    target = target_root / target_path
    source = target_root / source_path if source_path else None
    target_before = fingerprint_path(target)
    if target_before.kind not in {PathKind.MISSING, PathKind.FILE}:
        return [
            _conflict_action(
                target_root,
                target_path,
                source_path=source_path,
                reason="target path is not a regular file",
                evidence=(*evidence, f"target kind is {target_before.kind.value}"),
            )
        ]

    if target_before.kind is PathKind.FILE and target.read_bytes() == body:
        actions = [
            _keep_action(
                target_root,
                target_path,
                reason="canonical target already matches planned output",
            )
        ]
        if source is not None and source_path != target_path:
            actions.append(
                _delete_action(
                    target_root,
                    source_path,
                    reason=f"delete legacy duplicate after keeping {target_path}",
                )
            )
        return actions

    if target_before.kind is PathKind.FILE and not allow_existing_replace:
        choices = (ConflictChoice.SEMANTIC_MERGE,)
        if _ownership_for(target_path) is not OwnershipKind.PROJECT:
            choices = (
                ConflictChoice.ADOPT_TEMPLATE,
                ConflictChoice.SEMANTIC_MERGE,
            )
        return [
            _conflict_action(
                target_root,
                target_path,
                source_path=source_path,
                reason="canonical destination differs from planned migration output",
                evidence=(*evidence, "destination SHA-256 differs"),
                allowed_resolutions=choices,
            )
        ]

    is_merge = source_path is not None or allow_existing_replace
    action_id = _action_id("merge" if is_merge else "create", target_path)
    output_sha256 = _write_artifact(artifact_root, action_id, body)
    kind = ActionKind.MERGE if is_merge else ActionKind.CREATE
    return [
        PlannedAction(
            action_id=action_id,
            kind=kind,
            source_path=source_path,
            target_path=target_path,
            source_before=(fingerprint_path(source) if source is not None else None),
            target_before=target_before,
            output_sha256=output_sha256,
            ownership=_ownership_for(target_path),
            evidence=tuple(evidence),
            reason=reason,
            risk=(
                "writes a verified target before removing the legacy source"
                if source_path
                else "creates a new governed file"
            ),
            verification=("target SHA-256 equals planned output",)
            + (("legacy source is absent",) if source_path else ()),
            allowed_resolutions=(),
        )
    ]


def _render_project_spec(source: Path) -> bytes:
    text = source.read_text(encoding="utf-8")
    for legacy_reference, norn_reference in GOVERNANCE_REFERENCE_MAP.items():
        text = text.replace(legacy_reference, norn_reference)
    return text.encode("utf-8")


def _projected_directory_is_empty(
    target_root: Path,
    relative_path: str,
    removable_paths: set[str],
) -> bool:
    directory = target_root / relative_path
    if not directory.is_dir() or directory.is_symlink():
        return False
    for child in directory.iterdir():
        child_relative = child.relative_to(target_root).as_posix()
        if child_relative not in removable_paths:
            return False
    return True


def _append_directory_cleanup(
    target_root: Path,
    actions: list[PlannedAction],
) -> None:
    removable_paths = {
        action.source_path
        for action in actions
        if action.source_path and action.kind in {ActionKind.MERGE, ActionKind.MOVE}
    }
    removable_paths.update(
        action.target_path
        for action in actions
        if action.kind is ActionKind.DELETE and action.target_path in LEGACY_PATH_MAP
    )
    for directory in ("docs/spec", "docs/appendix"):
        if _projected_directory_is_empty(target_root, directory, removable_paths):
            actions.append(
                _delete_action(
                    target_root,
                    directory,
                    reason="remove legacy directory after all governed children move",
                )
            )
            removable_paths.add(directory)
    if _projected_directory_is_empty(target_root, "docs", removable_paths):
        actions.append(
            _delete_action(
                target_root,
                "docs",
                reason="remove legacy docs directory because it becomes empty",
            )
        )


def _analyze_uninitialized(
    target_root: Path,
    artifact_root: Path,
) -> list[PlannedAction]:
    actions: list[PlannedAction] = []
    source_root = asset_template_root()
    for relative_path in INITIALIZED_PATHS:
        actions.extend(
            _plan_output(
                target_root,
                artifact_root,
                target_path=relative_path,
                body=(source_root / relative_path).read_bytes(),
                reason="initialize current Norn governance structure",
                evidence=("governed target path is missing",),
            )
        )
    return actions


def _analyze_ambiguous(target_root: Path) -> list[PlannedAction]:
    actions: list[PlannedAction] = []
    for source_path, target_path in LEGACY_PATH_MAP.items():
        if not (target_root / source_path).exists():
            continue
        actions.append(
            _conflict_action(
                target_root,
                target_path,
                source_path=source_path,
                reason="insufficient legacy ownership evidence",
                evidence=(
                    "path name matches legacy layout but no known template hash or evidence chain exists",
                ),
                allowed_resolutions=(ConflictChoice.SEMANTIC_MERGE,),
            )
        )
    return actions


def _root_actions(
    target_root: Path,
    artifact_root: Path,
    structural_evidence: bool,
) -> list[PlannedAction]:
    current_root = asset_template_root() / ROOT_AGENTS
    target = target_root / ROOT_AGENTS
    if not target.exists():
        return _plan_output(
            target_root,
            artifact_root,
            target_path=ROOT_AGENTS,
            body=current_root.read_bytes(),
            reason="create the current Norn root entrypoint",
            evidence=("root AGENTS.md is missing",),
        )
    if _same_bytes(target, current_root):
        return [_keep_action(target_root, ROOT_AGENTS, reason="root entrypoint is current")]
    if _is_exact_legacy(target_root, ROOT_AGENTS):
        return _plan_output(
            target_root,
            artifact_root,
            target_path=ROOT_AGENTS,
            body=current_root.read_bytes(),
            reason="upgrade the exact legacy root entrypoint in place",
            evidence=("root SHA-256 matches legacy version 0",),
            allow_existing_replace=True,
        )
    if structural_evidence:
        return [
            _conflict_action(
                target_root,
                ROOT_AGENTS,
                reason="customized legacy root entrypoint requires semantic choice",
                evidence=("root participates in the complete legacy evidence chain",),
                allowed_resolutions=(
                    ConflictChoice.ADOPT_TEMPLATE,
                    ConflictChoice.SEMANTIC_MERGE,
                ),
            )
        ]
    return [
        _conflict_action(
            target_root,
            ROOT_AGENTS,
            reason="existing root AGENTS.md has no recognized Norn baseline",
            evidence=("root content differs from current and legacy templates",),
            allowed_resolutions=(ConflictChoice.SEMANTIC_MERGE,),
        )
    ]


def _analyze_legacy_or_mixed(
    target_root: Path,
    artifact_root: Path,
) -> list[PlannedAction]:
    actions: list[PlannedAction] = []
    structural_evidence = _has_structural_legacy_evidence(target_root)
    actions.extend(_root_actions(target_root, artifact_root, structural_evidence))

    current_root = asset_template_root()
    for source_path, target_path in LEGACY_PATH_MAP.items():
        source = target_root / source_path
        if not source.exists():
            target = target_root / target_path
            if target.is_file():
                if target_path.endswith("main-spec.md"):
                    actions.append(
                        _keep_action(
                            target_root,
                            target_path,
                            reason="project-owned specification already uses the Norn path",
                        )
                    )
                elif _same_bytes(target, current_root / target_path):
                    actions.append(
                        _keep_action(
                            target_root,
                            target_path,
                            reason="canonical governance target is current",
                        )
                    )
                else:
                    actions.append(
                        _conflict_action(
                            target_root,
                            target_path,
                            reason="partial Norn target has no matching migration source",
                            evidence=("target exists without manifest or legacy source",),
                            allowed_resolutions=(
                                ConflictChoice.ADOPT_TEMPLATE,
                                ConflictChoice.SEMANTIC_MERGE,
                            ),
                        )
                    )
                continue
            actions.extend(
                _plan_output(
                    target_root,
                    artifact_root,
                    target_path=target_path,
                    body=(current_root / target_path).read_bytes(),
                    reason="complete a missing Norn governance path",
                    evidence=("target and legacy source are both missing",),
                )
            )
            continue

        exact_legacy = _is_exact_legacy(target_root, source_path)
        if target_path.endswith("main-spec.md") and (exact_legacy or structural_evidence):
            actions.extend(
                _plan_output(
                    target_root,
                    artifact_root,
                    source_path=source_path,
                    target_path=target_path,
                    body=_render_project_spec(source),
                    reason="relocate the project-owned specification and update exact governance references",
                    evidence=(
                        "project specification ownership is confirmed by template hash or evidence chain",
                    ),
                )
            )
        elif exact_legacy:
            actions.extend(
                _plan_output(
                    target_root,
                    artifact_root,
                    source_path=source_path,
                    target_path=target_path,
                    body=(current_root / target_path).read_bytes(),
                    reason="upgrade and relocate an exact legacy governance template",
                    evidence=(f"{source_path} SHA-256 matches legacy version 0",),
                )
            )
        elif structural_evidence:
            actions.append(
                _conflict_action(
                    target_root,
                    target_path,
                    source_path=source_path,
                    reason="customized legacy governance requires semantic choice",
                    evidence=("complete structural legacy evidence chain is present",),
                    allowed_resolutions=(
                        ConflictChoice.ADOPT_TEMPLATE,
                        ConflictChoice.SEMANTIC_MERGE,
                    ),
                )
            )
        else:
            actions.append(
                _conflict_action(
                    target_root,
                    target_path,
                    source_path=source_path,
                    reason="insufficient legacy ownership evidence",
                    evidence=("isolated path does not match a known legacy template",),
                    allowed_resolutions=(ConflictChoice.SEMANTIC_MERGE,),
                )
            )

    if not any(action.kind is ActionKind.CONFLICT for action in actions):
        actions.extend(
            _plan_output(
                target_root,
                artifact_root,
                target_path=MANIFEST_PATH,
                body=(current_root / MANIFEST_PATH).read_bytes(),
                reason="write the current manifest after the migration plan is fully resolved",
                evidence=("all governed content actions are deterministic",),
            )
        )
    _append_directory_cleanup(target_root, actions)
    return actions


def _current_keep_actions(target_root: Path) -> list[PlannedAction]:
    return [
        _keep_action(target_root, path, reason="governed path is current")
        for path in INITIALIZED_PATHS
    ]


def _analyze_upgrade(
    target_root: Path,
    artifact_root: Path,
) -> list[PlannedAction]:
    manifest = load_manifest(target_root / MANIFEST_PATH)
    actions: list[PlannedAction] = []
    current_templates = asset_template_root()
    for relative_path, (ownership, block_ids) in MANAGED_PATHS.items():
        if ownership is OwnershipKind.PROJECT:
            actions.append(
                _keep_action(
                    target_root,
                    relative_path,
                    reason="project-owned specification is never replaced by upgrades",
                )
            )
            continue
        current_text = (target_root / relative_path).read_text(encoding="utf-8")
        current_blocks = parse_managed_blocks(current_text)
        block_id = block_ids[0]
        record = manifest.managed_files[relative_path]
        if current_blocks[block_id].sha256 != record.base_sha256:
            actions.append(
                _conflict_action(
                    target_root,
                    relative_path,
                    reason="managed block differs from recorded base",
                    evidence=(
                        "current managed block SHA-256 differs from the manifest baseline",
                    ),
                    allowed_resolutions=(
                        ConflictChoice.KEEP_CURRENT,
                        ConflictChoice.ADOPT_TEMPLATE,
                        ConflictChoice.SEMANTIC_MERGE,
                    ),
                )
            )
            continue
        template_text = (current_templates / relative_path).read_text(encoding="utf-8")
        template_block = parse_managed_blocks(template_text)[block_id].text
        rendered = replace_managed_block(current_text, block_id, template_block)
        actions.extend(
            _plan_output(
                target_root,
                artifact_root,
                target_path=relative_path,
                body=rendered.encode("utf-8"),
                reason="upgrade an unmodified managed block and preserve project text",
                evidence=("current block SHA-256 matches the recorded baseline",),
                allow_existing_replace=True,
            )
        )
    if not any(action.kind is ActionKind.CONFLICT for action in actions):
        actions.extend(
            _plan_output(
                target_root,
                artifact_root,
                target_path=MANIFEST_PATH,
                body=(current_templates / MANIFEST_PATH).read_bytes(),
                reason="advance the manifest after all managed blocks upgrade",
                evidence=("every managed block has a deterministic final baseline",),
                allow_existing_replace=True,
            )
        )
    return actions


def _resolved_plan_state(plan: GovernancePlan) -> ProjectState:
    if plan.project_state is ProjectState.UPGRADEABLE:
        return ProjectState.UPGRADEABLE
    if any(
        action.source_path and action.source_path.startswith("docs/")
        for action in plan.actions
    ):
        return ProjectState.LEGACY
    return ProjectState.MIXED


def _final_governed_body(
    target_root: Path,
    artifact_root: Path,
    actions: list[PlannedAction],
    relative_path: str,
) -> bytes:
    candidates = [
        action for action in actions if action.target_path == relative_path
    ]
    if len(candidates) != 1:
        raise ValueError(f"resolved plan must contain one action for {relative_path}")
    action = candidates[0]
    if action.output_sha256 is not None:
        artifact = artifact_root / "rendered" / f"{action.action_id}.content"
        body = artifact.read_bytes()
        if sha256_bytes(body) != action.output_sha256:
            raise ValueError(f"rendered artifact hash mismatch for {action.action_id}")
        return body
    path = target_root / relative_path
    if action.kind is ActionKind.KEEP and path.is_file():
        return path.read_bytes()
    raise ValueError(f"resolved action has no final body for {relative_path}")


def _resolved_manifest(
    target_root: Path,
    artifact_root: Path,
    actions: list[PlannedAction],
) -> NornManifest:
    records: dict[str, ManagedFileRecord] = {}
    for relative_path, (ownership, block_ids) in MANAGED_PATHS.items():
        body = _final_governed_body(
            target_root, artifact_root, actions, relative_path
        )
        if ownership is OwnershipKind.PROJECT:
            base_sha256 = None
        else:
            try:
                blocks = parse_managed_blocks(body.decode("utf-8"))
            except (UnicodeDecodeError, ManagedBlockError) as exc:
                raise ValueError(
                    f"invalid resolved managed content for {relative_path}: {exc}"
                ) from exc
            if tuple(blocks) != block_ids:
                raise ValueError(
                    f"resolved managed blocks mismatch for {relative_path}"
                )
            base_sha256 = blocks[block_ids[0]].sha256
        records[relative_path] = ManagedFileRecord(
            ownership=ownership,
            base_sha256=base_sha256,
            managed_blocks=block_ids,
            template_version=TEMPLATE_VERSION,
        )
    return NornManifest(
        schema_version=1,
        template_version=TEMPLATE_VERSION,
        managed_files=records,
    )


def resolve_conflicts(
    plan: GovernancePlan,
    choices: tuple[ConflictResolution, ...],
    artifact_root: Path,
) -> GovernancePlan:
    if plan.plan_sha256 != plan.expected_digest():
        raise ValueError("plan digest mismatch")
    artifact_root = Path(artifact_root).resolve()
    target_root = Path(plan.target_root)
    conflicts = {
        action.action_id: action
        for action in plan.actions
        if action.kind is ActionKind.CONFLICT
    }
    choice_map: dict[str, ConflictResolution] = {}
    for resolution in choices:
        if resolution.action_id in choice_map:
            raise ValueError(f"duplicate conflict choice: {resolution.action_id}")
        choice_map[resolution.action_id] = resolution
    if set(choice_map) != set(conflicts):
        missing = sorted(set(conflicts) - set(choice_map))
        extra = sorted(set(choice_map) - set(conflicts))
        raise ValueError(f"conflict choices mismatch: missing={missing}, extra={extra}")

    resolved_actions: list[PlannedAction] = []
    for action in plan.actions:
        if action.kind is not ActionKind.CONFLICT:
            if action.target_path != MANIFEST_PATH:
                resolved_actions.append(action)
            continue
        resolution = choice_map[action.action_id]
        if resolution.choice not in action.allowed_resolutions:
            raise ValueError(
                f"choice {resolution.choice.value} is not allowed for {action.action_id}"
            )
        if resolution.choice is ConflictChoice.KEEP_CURRENT:
            resolved_actions.append(
                PlannedAction(
                    action_id=action.action_id,
                    kind=ActionKind.KEEP,
                    source_path=None,
                    target_path=action.target_path,
                    source_before=None,
                    target_before=action.target_before,
                    output_sha256=None,
                    ownership=action.ownership,
                    evidence=(*action.evidence, "user chose to keep current managed block"),
                    reason="keep the current managed block as the accepted baseline",
                    risk="the current project customization becomes the new baseline",
                    verification=("target fingerprint remains unchanged",),
                    allowed_resolutions=(),
                )
            )
            continue

        if resolution.choice is ConflictChoice.ADOPT_TEMPLATE:
            if action.target_path not in MANAGED_PATHS:
                raise ValueError(
                    f"no canonical template for conflict {action.action_id}"
                )
            body = (asset_template_root() / action.target_path).read_bytes()
        else:
            assert resolution.rendered_path is not None
            semantic_path = Path(resolution.rendered_path).resolve()
            if not semantic_path.is_relative_to(artifact_root):
                raise ValueError("semantic artifact must stay inside artifact root")
            try:
                body = semantic_path.read_bytes()
                body.decode("utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise ValueError(f"invalid semantic artifact: {exc}") from exc
            if sha256_bytes(body) != resolution.rendered_sha256:
                raise ValueError("semantic artifact hash mismatch")
            if action.target_path in MANAGED_PATHS:
                _, expected_blocks = MANAGED_PATHS[action.target_path]
                if expected_blocks:
                    blocks = parse_managed_blocks(body.decode("utf-8"))
                    if tuple(blocks) != expected_blocks:
                        raise ValueError("semantic artifact managed blocks mismatch")

        output_sha256 = _write_artifact(artifact_root, action.action_id, body)
        kind = (
            ActionKind.MERGE
            if action.source_path or action.target_before.exists
            else ActionKind.CREATE
        )
        resolved_actions.append(
            PlannedAction(
                action_id=action.action_id,
                kind=kind,
                source_path=action.source_path,
                target_path=action.target_path,
                source_before=action.source_before,
                target_before=action.target_before,
                output_sha256=output_sha256,
                ownership=action.ownership,
                evidence=(*action.evidence, f"user chose {resolution.choice.value}"),
                reason="apply the explicitly resolved governance content",
                risk="writes only the user-selected, hash-bound result",
                verification=(
                    "target SHA-256 equals resolved output",
                )
                + (("legacy source is absent",) if action.source_path else ()),
                allowed_resolutions=(),
            )
        )

    directory_paths = {"docs/spec", "docs/appendix", "docs"}
    resolved_actions = [
        action
        for action in resolved_actions
        if not (
            action.kind is ActionKind.DELETE
            and action.target_path in directory_paths
        )
    ]
    _append_directory_cleanup(target_root, resolved_actions)
    manifest = _resolved_manifest(target_root, artifact_root, resolved_actions)
    manifest_body = manifest_bytes(manifest)
    manifest_action_id = _action_id("merge", MANIFEST_PATH)
    manifest_sha256 = _write_artifact(
        artifact_root, manifest_action_id, manifest_body
    )
    manifest_before = fingerprint_path(target_root / MANIFEST_PATH)
    resolved_actions.append(
        PlannedAction(
            action_id=manifest_action_id,
            kind=(
                ActionKind.MERGE if manifest_before.exists else ActionKind.CREATE
            ),
            source_path=None,
            target_path=MANIFEST_PATH,
            source_before=None,
            target_before=manifest_before,
            output_sha256=manifest_sha256,
            ownership=OwnershipKind.MANAGED,
            evidence=("every conflict has an explicit validated resolution",),
            reason="record final managed baselines after conflict resolution",
            risk="marks the migration or upgrade complete only after apply succeeds",
            verification=("manifest bytes and managed baselines match final content",),
            allowed_resolutions=(),
        )
    )
    resolved = GovernancePlan.build(
        target_root=plan.target_root,
        project_state=_resolved_plan_state(plan),
        template_version=TEMPLATE_VERSION,
        actions=resolved_actions,
        conflicts=(),
    )
    write_plan(resolved, artifact_root)
    return resolved


def _blocking_state_actions(
    target_root: Path,
    state: ProjectState,
) -> list[PlannedAction]:
    if state is ProjectState.AMBIGUOUS:
        return _analyze_ambiguous(target_root)
    for relative_path in (ROOT_AGENTS, MANIFEST_PATH, *LEGACY_PATH_MAP):
        fingerprint = fingerprint_path(target_root / relative_path)
        if fingerprint.kind in {
            PathKind.DIRECTORY,
            PathKind.SYMLINK,
            PathKind.OTHER,
        }:
            return [
                _conflict_action(
                    target_root,
                    relative_path,
                    reason="governed path has an unsupported filesystem type",
                    evidence=(f"observed path kind is {fingerprint.kind.value}",),
                )
            ]
    if (target_root / MANIFEST_PATH).exists():
        return [
            _conflict_action(
                target_root,
                MANIFEST_PATH,
                reason="manifest is invalid or newer than this skill",
                evidence=("manifest validation or version compatibility failed",),
            )
        ]
    return [
        _conflict_action(
            target_root,
            ROOT_AGENTS,
            reason="existing root AGENTS.md has no recognized Norn baseline",
            evidence=("root content differs from current and legacy templates",),
            allowed_resolutions=(ConflictChoice.SEMANTIC_MERGE,),
        )
    ]


def analyze_governance(target_root: Path, artifact_root: Path) -> GovernancePlan:
    target_root = Path(target_root).resolve()
    artifact_root = Path(artifact_root).resolve()
    if not target_root.is_dir():
        raise ValueError(f"target root is not a directory: {target_root}")
    if artifact_root == target_root or artifact_root.is_relative_to(target_root):
        raise ValueError("artifact root must be outside the target repository")
    artifact_root.mkdir(parents=True, exist_ok=True)
    state = classify_project(target_root)

    if state is ProjectState.UNINITIALIZED:
        actions = _analyze_uninitialized(target_root, artifact_root)
    elif state is ProjectState.CURRENT:
        actions = _current_keep_actions(target_root)
    elif state is ProjectState.UPGRADEABLE:
        actions = _analyze_upgrade(target_root, artifact_root)
    elif state is ProjectState.AMBIGUOUS:
        actions = _analyze_ambiguous(target_root)
    elif any((target_root / path).exists() for path in LEGACY_PATH_MAP):
        actions = _analyze_legacy_or_mixed(target_root, artifact_root)
    elif state is ProjectState.MIXED:
        actions = _analyze_legacy_or_mixed(target_root, artifact_root)
    else:
        actions = _blocking_state_actions(target_root, state)

    if any(action.kind is ActionKind.CONFLICT for action in actions):
        effective_state = (
            ProjectState.AMBIGUOUS
            if state is ProjectState.AMBIGUOUS
            else ProjectState.CONFLICT
        )
    else:
        effective_state = state
    conflicts = tuple(
        f"{action.target_path}: {action.reason}"
        for action in actions
        if action.kind is ActionKind.CONFLICT
    )
    plan = GovernancePlan.build(
        target_root=str(target_root),
        project_state=effective_state,
        template_version=TEMPLATE_VERSION,
        actions=actions,
        conflicts=conflicts,
    )
    write_plan(plan, artifact_root)
    return plan
