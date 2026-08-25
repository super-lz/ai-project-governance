from __future__ import annotations

import json
import hashlib
import shutil
import os
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from norn_governance.models import (  # noqa: E402
    ActionKind,
    ConflictChoice,
    GovernancePlan,
    ManagedFileRecord,
    NornManifest,
    OwnershipKind,
    PathFingerprint,
    PathKind,
    PlannedAction,
    ProjectState,
    load_plan,
    write_plan,
)
from norn_governance.analyzer import (  # noqa: E402
    analyze_governance,
    classify_project,
    fingerprint_path,
)
from norn_governance.templates import MANAGED_PATHS, asset_template_root  # noqa: E402


class PlanModelTests(unittest.TestCase):
    def make_action(self) -> PlannedAction:
        return PlannedAction(
            action_id="create-root-agents",
            kind=ActionKind.CREATE,
            source_path=None,
            target_path="AGENTS.md",
            source_before=None,
            target_before=PathFingerprint.missing(),
            output_sha256="a" * 64,
            ownership=OwnershipKind.MANAGED,
            evidence=("target path is missing",),
            reason="initialize Norn entrypoint",
            risk="creates a new file",
            verification=("target SHA-256 equals planned output",),
            allowed_resolutions=(),
        )

    def make_plan(self) -> GovernancePlan:
        return GovernancePlan.build(
            target_root="/tmp/example",
            project_state=ProjectState.UNINITIALIZED,
            template_version=1,
            actions=(self.make_action(),),
            conflicts=(),
        )

    def test_plan_digest_is_stable_and_excludes_its_own_digest(self) -> None:
        first = self.make_plan()
        second = self.make_plan()

        self.assertEqual(len(first.plan_sha256), 64)
        self.assertEqual(first.plan_sha256, second.plan_sha256)
        self.assertEqual(first.to_dict()["plan_sha256"], first.plan_sha256)
        self.assertEqual(
            GovernancePlan.from_dict(first.to_dict()).to_dict(), first.to_dict()
        )

    def test_tampered_plan_digest_is_rejected(self) -> None:
        payload = self.make_plan().to_dict()
        payload["template_version"] = 2

        with self.assertRaisesRegex(ValueError, "plan digest mismatch"):
            GovernancePlan.from_dict(payload)

    def test_plan_json_uses_enum_values_and_immutable_collections(self) -> None:
        plan = self.make_plan()
        payload = plan.to_dict()

        self.assertEqual(payload["project_state"], "uninitialized")
        self.assertEqual(payload["actions"][0]["kind"], "create")
        self.assertEqual(payload["actions"][0]["ownership"], "managed")
        self.assertIsInstance(plan.actions, tuple)
        self.assertIsInstance(plan.actions[0].evidence, tuple)
        with self.assertRaises(FrozenInstanceError):
            plan.template_version = 2  # type: ignore[misc]

    def test_path_fingerprints_distinguish_missing_file_and_directory(self) -> None:
        missing = PathFingerprint.missing()
        file_path = PathFingerprint(True, PathKind.FILE, "b" * 64)
        directory = PathFingerprint(True, PathKind.DIRECTORY, "c" * 64)

        self.assertEqual(missing.to_dict(), {"exists": False, "kind": "missing", "sha256": None})
        self.assertEqual(file_path.to_dict()["kind"], "file")
        self.assertEqual(directory.to_dict()["kind"], "directory")

    def test_write_and_load_plan_round_trip_and_reject_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan_path = write_plan(self.make_plan(), Path(directory))
            self.assertEqual(plan_path.name, "plan.json")
            self.assertEqual(load_plan(plan_path).to_dict(), self.make_plan().to_dict())

            payload = json.loads(plan_path.read_text(encoding="utf-8"))
            payload["project_state"] = "current"
            plan_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "plan digest mismatch"):
                load_plan(plan_path)

    def test_write_rejects_plan_with_invalid_digest(self) -> None:
        invalid = replace(self.make_plan(), plan_sha256="f" * 64)

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "plan digest mismatch"):
                write_plan(invalid, Path(directory))
            self.assertFalse((Path(directory) / "plan.json").exists())


class ManifestModelTests(unittest.TestCase):
    def make_manifest(self) -> NornManifest:
        return NornManifest(
            schema_version=1,
            template_version=1,
            managed_files={
                "AGENTS.md": ManagedFileRecord(
                    ownership=OwnershipKind.MIXED,
                    base_sha256="d" * 64,
                    managed_blocks=("core-governance",),
                    template_version=1,
                ),
                "norn-governance/spec/main-spec.md": ManagedFileRecord(
                    ownership=OwnershipKind.PROJECT,
                    base_sha256=None,
                    managed_blocks=(),
                    template_version=1,
                ),
            },
        )

    def test_manifest_round_trip_is_sorted_and_immutable(self) -> None:
        manifest = self.make_manifest()
        restored = NornManifest.from_dict(manifest.to_dict())

        self.assertEqual(restored.to_dict(), manifest.to_dict())
        self.assertEqual(list(manifest.managed_files), sorted(manifest.managed_files))
        with self.assertRaises(TypeError):
            manifest.managed_files["other.md"] = manifest.managed_files["AGENTS.md"]  # type: ignore[index]

    def test_manifest_rejects_invalid_contract_values(self) -> None:
        valid = self.make_manifest().to_dict()
        cases = [
            ({**valid, "schema_version": 2}, "unsupported manifest schema"),
            ({**valid, "template_version": -1}, "template_version"),
            (
                {
                    **valid,
                    "managed_files": {
                        **valid["managed_files"],
                        "AGENTS.md": {
                            **valid["managed_files"]["AGENTS.md"],
                            "ownership": "unknown",
                        },
                    },
                },
                "ownership",
            ),
            (
                {
                    **valid,
                    "managed_files": {
                        **valid["managed_files"],
                        "AGENTS.md": {
                            **valid["managed_files"]["AGENTS.md"],
                            "base_sha256": "short",
                        },
                    },
                },
                "base_sha256",
            ),
            (
                {
                    **valid,
                    "managed_files": {
                        **valid["managed_files"],
                        "AGENTS.md": {
                            **valid["managed_files"]["AGENTS.md"],
                            "managed_blocks": [],
                        },
                    },
                },
                "managed_blocks",
            ),
        ]

        for payload, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    NornManifest.from_dict(payload)

    def test_resolvable_conflict_preserves_explicit_allowed_choices(self) -> None:
        action = self.make_conflict_action()

        self.assertEqual(
            action.allowed_resolutions,
            (ConflictChoice.ADOPT_TEMPLATE, ConflictChoice.SEMANTIC_MERGE),
        )

    def test_blocking_conflict_can_require_external_change_and_reanalysis(self) -> None:
        action = replace(self.make_conflict_action(), allowed_resolutions=())

        self.assertEqual(action.kind, ActionKind.CONFLICT)
        self.assertEqual(action.allowed_resolutions, ())

    def make_conflict_action(self) -> PlannedAction:
        return PlannedAction(
            action_id="merge-root-agents",
            kind=ActionKind.CONFLICT,
            source_path=None,
            target_path="AGENTS.md",
            source_before=None,
            target_before=PathFingerprint(True, PathKind.FILE, "e" * 64),
            output_sha256=None,
            ownership=OwnershipKind.MIXED,
            evidence=("managed block differs",),
            reason="requires semantic choice",
            risk="project rules could be lost",
            verification=("choice is represented in a resolved plan",),
            allowed_resolutions=(
                ConflictChoice.ADOPT_TEMPLATE,
                ConflictChoice.SEMANTIC_MERGE,
            ),
        )


class GovernanceAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary_directory.name)
        self.asset_root = asset_template_root()
        self.legacy_root = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "legacy-templates"
            / "0"
        )
        self.artifact_counter = 0

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def make_target(self) -> Path:
        target = self.workspace / f"target-{len(tuple(self.workspace.glob('target-*')))}"
        target.mkdir()
        return target

    def artifacts(self) -> Path:
        self.artifact_counter += 1
        return self.workspace / f"artifacts-{self.artifact_counter}"

    def write(self, target: Path, relative_path: str, text: str) -> None:
        path = target / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def append(self, target: Path, relative_path: str, text: str) -> None:
        path = target / relative_path
        path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")

    def copy_current_template(self) -> Path:
        target = self.make_target()
        shutil.copytree(self.asset_root, target, dirs_exist_ok=True)
        return target

    def copy_legacy_template(self) -> Path:
        target = self.make_target()
        shutil.copytree(self.legacy_root, target, dirs_exist_ok=True)
        return target

    def snapshot(self, target: Path) -> dict[str, bytes]:
        return {
            path.relative_to(target).as_posix(): path.read_bytes()
            for path in target.rglob("*")
            if path.is_file()
        }

    def action_for(
        self,
        plan: GovernancePlan,
        target_path: str,
        kind: ActionKind | None = None,
    ) -> PlannedAction:
        matches = [
            action
            for action in plan.actions
            if action.target_path == target_path
            and (kind is None or action.kind is kind)
        ]
        self.assertEqual(len(matches), 1, (target_path, kind, plan.to_dict()))
        return matches[0]

    def rendered_text(self, artifacts: Path, action: PlannedAction) -> str:
        path = artifacts / "rendered" / f"{action.action_id}.content"
        body = path.read_bytes()
        self.assertEqual(hashlib.sha256(body).hexdigest(), action.output_sha256)
        return body.decode("utf-8")

    def test_fingerprint_path_distinguishes_supported_path_kinds(self) -> None:
        target = self.make_target()
        file_path = target / "file.md"
        file_path.write_text("content\n", encoding="utf-8")
        directory_path = target / "directory"
        directory_path.mkdir()
        (directory_path / "child.txt").write_text("child\n", encoding="utf-8")

        self.assertEqual(fingerprint_path(target / "missing").kind, PathKind.MISSING)
        self.assertEqual(
            fingerprint_path(file_path).sha256,
            hashlib.sha256(b"content\n").hexdigest(),
        )
        first_directory_hash = fingerprint_path(directory_path).sha256
        (directory_path / "second.txt").write_text("second\n", encoding="utf-8")
        self.assertNotEqual(fingerprint_path(directory_path).sha256, first_directory_hash)

    def test_empty_project_is_uninitialized_and_analysis_is_read_only(self) -> None:
        target = self.make_target()
        artifacts = self.artifacts()
        before = self.snapshot(target)

        plan = analyze_governance(target, artifacts)

        self.assertEqual(plan.project_state, ProjectState.UNINITIALIZED)
        self.assertEqual(self.snapshot(target), before)
        self.assertEqual(
            {
                action.target_path
                for action in plan.actions
                if action.kind is ActionKind.CREATE
            },
            {*MANAGED_PATHS, "norn-governance/.norn.json"},
        )
        self.assertEqual(load_plan(artifacts / "plan.json").to_dict(), plan.to_dict())

    def test_current_project_has_only_keep_actions(self) -> None:
        target = self.copy_current_template()

        self.assertEqual(classify_project(target), ProjectState.CURRENT)
        plan = analyze_governance(target, self.artifacts())

        self.assertEqual(plan.project_state, ProjectState.CURRENT)
        self.assertTrue(plan.actions)
        self.assertTrue(all(action.kind is ActionKind.KEEP for action in plan.actions))

    def test_isolated_legacy_named_spec_is_ambiguous(self) -> None:
        target = self.make_target()
        self.write(target, "docs/spec/main-spec.md", "# Existing product spec\n")

        plan = analyze_governance(target, self.artifacts())

        self.assertEqual(plan.project_state, ProjectState.AMBIGUOUS)
        self.assertEqual(plan.actions[0].kind, ActionKind.CONFLICT)
        self.assertIn("insufficient legacy ownership evidence", plan.actions[0].reason)

    def test_partial_exact_legacy_files_are_mixed_not_ambiguous(self) -> None:
        target = self.make_target()
        source = self.legacy_root / "docs/spec/main-spec.md"
        destination = target / "docs/spec/main-spec.md"
        destination.parent.mkdir(parents=True)
        shutil.copy2(source, destination)

        plan = analyze_governance(target, self.artifacts())

        self.assertEqual(plan.project_state, ProjectState.MIXED)

    def test_complete_legacy_bundle_builds_hashed_merge_artifacts(self) -> None:
        target = self.copy_legacy_template()
        artifacts = self.artifacts()
        before = self.snapshot(target)

        plan = analyze_governance(target, artifacts)

        self.assertEqual(plan.project_state, ProjectState.LEGACY)
        self.assertEqual(self.snapshot(target), before)
        self.assertEqual(
            {
                (action.source_path, action.target_path, action.kind)
                for action in plan.actions
                if action.source_path
            },
            {
                (
                    "docs/AGENTS.md",
                    "norn-governance/AGENTS.md",
                    ActionKind.MERGE,
                ),
                (
                    "docs/spec/AGENTS.md",
                    "norn-governance/spec/AGENTS.md",
                    ActionKind.MERGE,
                ),
                (
                    "docs/spec/main-spec.md",
                    "norn-governance/spec/main-spec.md",
                    ActionKind.MERGE,
                ),
                (
                    "docs/appendix/README.md",
                    "norn-governance/appendix/README.md",
                    ActionKind.MERGE,
                ),
            },
        )
        for action in plan.actions:
            if action.output_sha256:
                self.rendered_text(artifacts, action)

    def test_customized_main_spec_and_other_docs_are_preserved(self) -> None:
        target = self.copy_legacy_template()
        self.append(
            target,
            "docs/spec/main-spec.md",
            "\n## Business Contract\nOrder state remains durable.\n",
        )
        self.write(target, "docs/architecture.md", "project-owned\n")
        artifacts = self.artifacts()

        plan = analyze_governance(target, artifacts)

        self.assertEqual(plan.project_state, ProjectState.LEGACY)
        spec_action = self.action_for(
            plan, "norn-governance/spec/main-spec.md", ActionKind.MERGE
        )
        rendered = self.rendered_text(artifacts, spec_action)
        self.assertIn("Order state remains durable.", rendered)
        self.assertIn("norn-governance/spec/AGENTS.md", rendered)
        self.assertNotIn(
            "docs/architecture.md",
            {
                path
                for action in plan.actions
                for path in (action.source_path, action.target_path)
                if path
            },
        )
        self.assertFalse(
            any(
                action.kind is ActionKind.DELETE and action.target_path == "docs"
                for action in plan.actions
            )
        )

    def test_customized_legacy_governance_requires_semantic_choice(self) -> None:
        target = self.copy_legacy_template()
        self.append(target, "docs/AGENTS.md", "\n## Project Rule\nKeep this.\n")

        plan = analyze_governance(target, self.artifacts())

        self.assertEqual(plan.project_state, ProjectState.CONFLICT)
        action = self.action_for(plan, "norn-governance/AGENTS.md")
        self.assertEqual(action.kind, ActionKind.CONFLICT)
        self.assertEqual(
            action.allowed_resolutions,
            (ConflictChoice.ADOPT_TEMPLATE, ConflictChoice.SEMANTIC_MERGE),
        )
        self.assertFalse(
            any(
                action.target_path == "norn-governance/.norn.json"
                for action in plan.actions
            )
        )

    def test_equal_destination_is_kept_and_duplicate_source_is_deleted(self) -> None:
        target = self.copy_legacy_template()
        destination = target / "norn-governance/AGENTS.md"
        destination.parent.mkdir(parents=True)
        shutil.copy2(self.asset_root / "norn-governance/AGENTS.md", destination)

        plan = analyze_governance(target, self.artifacts())

        self.action_for(plan, "norn-governance/AGENTS.md", ActionKind.KEEP)
        duplicate_delete = self.action_for(plan, "docs/AGENTS.md", ActionKind.DELETE)
        self.assertEqual(duplicate_delete.output_sha256, None)

    def test_current_and_legacy_paths_are_mixed(self) -> None:
        target = self.copy_current_template()
        legacy = self.legacy_root / "docs/spec/main-spec.md"
        destination = target / "docs/spec/main-spec.md"
        destination.parent.mkdir(parents=True)
        shutil.copy2(legacy, destination)

        self.assertEqual(classify_project(target), ProjectState.MIXED)

    def test_current_root_with_exact_legacy_bundle_is_recoverable_mixed_state(self) -> None:
        target = self.copy_legacy_template()
        shutil.copy2(self.asset_root / "AGENTS.md", target / "AGENTS.md")

        plan = analyze_governance(target, self.artifacts())

        self.assertEqual(plan.project_state, ProjectState.MIXED)
        self.assertFalse(plan.conflicts)
        self.assertEqual(
            self.action_for(plan, "AGENTS.md").kind,
            ActionKind.KEEP,
        )

    def test_future_manifest_and_directory_at_file_path_are_conflicts(self) -> None:
        future = self.copy_current_template()
        manifest_path = future / "norn-governance/.norn.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["template_version"] = 99
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        directory_conflict = self.make_target()
        (directory_conflict / "AGENTS.md").mkdir()

        self.assertEqual(classify_project(future), ProjectState.CONFLICT)
        self.assertEqual(
            classify_project(directory_conflict), ProjectState.CONFLICT
        )

    def test_manifest_record_version_must_match_manifest_version(self) -> None:
        target = self.copy_current_template()
        manifest_path = target / "norn-governance/.norn.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["managed_files"]["AGENTS.md"]["template_version"] = 0
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        self.assertEqual(classify_project(target), ProjectState.CONFLICT)

    def test_symlinked_governance_parent_is_a_conflict(self) -> None:
        target = self.make_target()
        shutil.copy2(self.asset_root / "AGENTS.md", target / "AGENTS.md")
        os.symlink(
            self.asset_root / "norn-governance",
            target / "norn-governance",
            target_is_directory=True,
        )

        self.assertEqual(classify_project(target), ProjectState.CONFLICT)


if __name__ == "__main__":
    unittest.main()
