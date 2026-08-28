from __future__ import annotations

import errno
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .analyzer import classify_project, fingerprint_path
from .models import ActionKind, GovernanceTransaction, TransactionAction, ProjectState, load_transaction
from .templates import INITIALIZED_PATHS, MANIFEST_PATH, TEMPLATE_VERSION, load_manifest


class TransactionPreconditionError(RuntimeError):
    """Raised before writes when the analyzed repository state changed."""


class TransactionArtifactError(RuntimeError):
    """Raised when a governance transaction or rendered output cannot be trusted."""


class TransactionConflictError(RuntimeError):
    """Raised when a governance transaction still contains unresolved conflicts."""


@dataclass(frozen=True)
class VerificationResult:
    state: ProjectState
    manifest_valid: bool
    single_spec_source: bool
    checked_paths: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ApplyResult:
    created: tuple[str, ...]
    updated: tuple[str, ...]
    removed: tuple[str, ...]
    removed_directories: tuple[str, ...]
    verification: VerificationResult


def _safe_repository_path(target_root: Path, relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise TransactionPreconditionError(f"unsafe relative path: {relative_path}")
    candidate = target_root.joinpath(*path.parts)
    current = target_root
    for part in path.parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise TransactionPreconditionError(
                f"symlink in governed path parent: {current.relative_to(target_root)}"
            )
        if current.exists() and not current.is_dir():
            raise TransactionPreconditionError(
                f"non-directory governed path parent: {current.relative_to(target_root)}"
            )
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(target_root):
        raise TransactionPreconditionError(f"path escapes target root: {relative_path}")
    if candidate.is_symlink():
        raise TransactionPreconditionError(f"governed path is a symlink: {relative_path}")
    return candidate


def _load_valid_transaction(transaction_path: Path) -> GovernanceTransaction:
    try:
        transaction = load_transaction(transaction_path)
    except ValueError as exc:
        raise TransactionArtifactError(str(exc)) from exc
    if transaction.conflicts or any(
        action.kind is ActionKind.CONFLICT for action in transaction.actions
    ):
        raise TransactionConflictError("transaction contains unresolved conflict actions")
    return transaction


def _validate_transaction_paths(transaction: GovernanceTransaction) -> Path:
    target_root = Path(transaction.target_root)
    resolved_root = target_root.resolve(strict=True)
    if target_root != resolved_root or not resolved_root.is_dir():
        raise TransactionPreconditionError(
            "transaction target root is not a canonical directory"
        )
    mutating_targets: set[str] = set()
    for action in transaction.actions:
        _safe_repository_path(resolved_root, action.target_path)
        if action.source_path is not None:
            _safe_repository_path(resolved_root, action.source_path)
            if action.source_path == action.target_path:
                raise TransactionPreconditionError(
                    f"source and target paths are identical: {action.target_path}"
                )
        if action.kind in {
            ActionKind.CREATE,
            ActionKind.MOVE,
            ActionKind.MERGE,
            ActionKind.DELETE,
        }:
            if action.target_path in mutating_targets:
                raise TransactionPreconditionError(
                    f"multiple mutating actions target {action.target_path}"
                )
            mutating_targets.add(action.target_path)
    return resolved_root


def _validate_all_preconditions(
    transaction: GovernanceTransaction,
    target_root: Path,
) -> None:
    for action in transaction.actions:
        target = _safe_repository_path(target_root, action.target_path)
        if fingerprint_path(target) != action.target_before:
            raise TransactionPreconditionError(
                f"fingerprint changed for target {action.target_path}"
            )
        if action.source_path is not None:
            assert action.source_before is not None
            source = _safe_repository_path(target_root, action.source_path)
            if fingerprint_path(source) != action.source_before:
                raise TransactionPreconditionError(
                    f"fingerprint changed for source {action.source_path}"
                )


def _validate_rendered_artifacts(
    transaction: GovernanceTransaction,
    artifact_root: Path,
) -> dict[str, bytes]:
    rendered_root = artifact_root / "rendered"
    rendered: dict[str, bytes] = {}
    for action in transaction.actions:
        if action.output_sha256 is None:
            continue
        artifact = rendered_root / f"{action.action_id}.content"
        if artifact.is_symlink() or not artifact.is_file():
            raise TransactionArtifactError(
                f"rendered artifact missing or unsafe for {action.action_id}"
            )
        body = artifact.read_bytes()
        from .models import sha256_bytes

        if sha256_bytes(body) != action.output_sha256:
            raise TransactionArtifactError(
                f"rendered artifact hash mismatch for {action.action_id}"
            )
        rendered[action.action_id] = body
    return rendered


def _stage_outputs(rendered: dict[str, bytes], staging_root: Path) -> dict[str, Path]:
    staged: dict[str, Path] = {}
    for action_id, body in rendered.items():
        path = staging_root / f"{action_id}.content"
        with path.open("wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        staged[action_id] = path
    return staged


def _target_mode(action: TransactionAction, target_root: Path) -> int:
    target = target_root / action.target_path
    if target.is_file() and not target.is_symlink():
        return stat.S_IMODE(os.stat(target, follow_symlinks=False).st_mode)
    if action.source_path is not None:
        source = target_root / action.source_path
        if source.is_file() and not source.is_symlink():
            return stat.S_IMODE(os.stat(source, follow_symlinks=False).st_mode)
    return 0o644


def _atomic_replace_target(
    action: TransactionAction,
    target_root: Path,
    staged_path: Path,
) -> None:
    target = _safe_repository_path(target_root, action.target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    _safe_repository_path(target_root, action.target_path)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".norn-tmp", dir=target.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(staged_path.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, _target_mode(action, target_root))
        os.replace(temporary_path, target)
        directory_descriptor = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    if fingerprint_path(target).sha256 != action.output_sha256:
        raise TransactionArtifactError(
            f"target hash mismatch after replace for {action.target_path}"
        )


def _verify_written_targets(
    actions: tuple[TransactionAction, ...],
    target_root: Path,
) -> None:
    for action in actions:
        if action.output_sha256 is None or action.target_path == MANIFEST_PATH:
            continue
        if fingerprint_path(target_root / action.target_path).sha256 != action.output_sha256:
            raise TransactionArtifactError(
                f"target hash mismatch before source deletion for {action.target_path}"
            )


def _remove_sources_and_files(
    actions: tuple[TransactionAction, ...],
    target_root: Path,
) -> list[str]:
    removed: list[str] = []
    for action in actions:
        if action.source_path is None or action.kind not in {
            ActionKind.MOVE,
            ActionKind.MERGE,
        }:
            continue
        target = target_root / action.target_path
        if fingerprint_path(target).sha256 != action.output_sha256:
            raise TransactionArtifactError(
                f"target hash mismatch before deleting {action.source_path}"
            )
        source = _safe_repository_path(target_root, action.source_path)
        if fingerprint_path(source) != action.source_before:
            raise TransactionPreconditionError(
                f"fingerprint changed before deletion for source {action.source_path}"
            )
        source.unlink()
        removed.append(action.source_path)

    for action in actions:
        if action.kind is not ActionKind.DELETE:
            continue
        target = _safe_repository_path(target_root, action.target_path)
        if action.target_before.kind.value != "file":
            continue
        if target.exists():
            if fingerprint_path(target) != action.target_before:
                raise TransactionPreconditionError(
                    "fingerprint changed before deletion for target "
                    f"{action.target_path}"
                )
            target.unlink()
            removed.append(action.target_path)
    return removed


def _remove_directories(
    actions: tuple[TransactionAction, ...],
    target_root: Path,
) -> tuple[list[str], list[str]]:
    removed: list[str] = []
    warnings: list[str] = []
    directory_actions = sorted(
        (
            action
            for action in actions
            if action.kind is ActionKind.DELETE
            and action.target_before.kind.value == "directory"
        ),
        key=lambda action: len(Path(action.target_path).parts),
        reverse=True,
    )
    for action in directory_actions:
        target = _safe_repository_path(target_root, action.target_path)
        try:
            target.rmdir()
            removed.append(action.target_path)
        except OSError as exc:
            if exc.errno in {errno.ENOTEMPTY, errno.EEXIST}:
                warnings.append(f"preserved non-empty directory: {action.target_path}")
                continue
            raise
    return removed, warnings


def verify_governance(
    target_root: Path,
    *,
    warnings: tuple[str, ...] = (),
) -> VerificationResult:
    target_root = Path(target_root).resolve()
    state = classify_project(target_root)
    try:
        manifest = load_manifest(target_root / MANIFEST_PATH)
        manifest_valid = manifest.template_version == TEMPLATE_VERSION
    except ValueError:
        manifest_valid = False
    legacy_spec = target_root / "docs/spec/main-spec.md"
    current_spec = target_root / "norn-governance/spec/main-spec.md"
    single_spec_source = current_spec.is_file() and not legacy_spec.exists()
    return VerificationResult(
        state=state,
        manifest_valid=manifest_valid,
        single_spec_source=single_spec_source,
        checked_paths=tuple(INITIALIZED_PATHS),
        warnings=warnings,
    )


def apply_transaction(transaction_path: Path) -> ApplyResult:
    transaction_path = Path(transaction_path).resolve()
    transaction = _load_valid_transaction(transaction_path)
    target_root = _validate_transaction_paths(transaction)
    _validate_all_preconditions(transaction, target_root)
    rendered = _validate_rendered_artifacts(transaction, transaction_path.parent)

    created: list[str] = []
    updated: list[str] = []
    with tempfile.TemporaryDirectory(prefix="norn-governance-stage-") as directory:
        staged = _stage_outputs(rendered, Path(directory))
        non_manifest_actions = tuple(
            action
            for action in transaction.actions
            if action.output_sha256 is not None
            and action.target_path != MANIFEST_PATH
        )
        for action in non_manifest_actions:
            _atomic_replace_target(action, target_root, staged[action.action_id])
            if action.target_before.exists:
                updated.append(action.target_path)
            else:
                created.append(action.target_path)

        _verify_written_targets(transaction.actions, target_root)
        removed = _remove_sources_and_files(transaction.actions, target_root)
        removed_directories, warnings = _remove_directories(
            transaction.actions, target_root
        )

        manifest_actions = [
            action
            for action in transaction.actions
            if action.output_sha256 is not None
            and action.target_path == MANIFEST_PATH
        ]
        if len(manifest_actions) > 1:
            raise TransactionPreconditionError(
                "transaction contains multiple manifest writes"
            )
        if manifest_actions:
            action = manifest_actions[0]
            _atomic_replace_target(action, target_root, staged[action.action_id])
            if action.target_before.exists:
                updated.append(action.target_path)
            else:
                created.append(action.target_path)

    verification = verify_governance(
        target_root, warnings=tuple(warnings)
    )
    if not (
        verification.state is ProjectState.CURRENT
        and verification.manifest_valid
        and verification.single_spec_source
    ):
        raise TransactionArtifactError(
            "post-apply governance verification failed: "
            f"state={verification.state.value}, "
            f"manifest_valid={verification.manifest_valid}, "
            f"single_spec_source={verification.single_spec_source}"
        )
    return ApplyResult(
        created=tuple(created),
        updated=tuple(updated),
        removed=tuple(removed),
        removed_directories=tuple(removed_directories),
        verification=verification,
    )
