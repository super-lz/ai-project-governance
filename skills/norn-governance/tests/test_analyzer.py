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
    ConflictResolution,
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
    resolve_conflicts,
)
from norn_governance.templates import MANAGED_PATHS, asset_template_root  # noqa: E402
from norn_governance.managed_markdown import (  # noqa: E402
    parse_managed_blocks,
    replace_managed_block,
)


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

    def copy_versioned_project(self) -> Path:
        target = self.copy_current_template()
        root_path = target / "AGENTS.md"
        old_block = (
            "<!-- norn:managed:start core-governance -->\n"
            "# Prior Core Governance\n\nLegacy managed rules.\n"
            "<!-- norn:managed:end core-governance -->"
        )
        root_path.write_text(
            replace_managed_block(
                root_path.read_text(encoding="utf-8"),
                "core-governance",
                old_block,
            ),
            encoding="utf-8",
        )
        manifest_path = target / "norn-governance/.norn.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["template_version"] = 0
        for record in manifest["managed_files"].values():
            record["template_version"] = 0
        manifest["managed_files"]["AGENTS.md"]["base_sha256"] = hashlib.sha256(
            old_block.encode("utf-8")
        ).hexdigest()
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
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

    def test_custom_root_can_resolve_initialization_without_missing_actions(self) -> None:
        target = self.make_target()
        self.write(target, "AGENTS.md", "# Existing project rules\n\nKeep this.\n")
        artifacts = self.artifacts()
        original = analyze_governance(target, artifacts)
        conflict = self.action_for(
            original,
            "AGENTS.md",
            ActionKind.CONFLICT,
        )
        semantic_path = artifacts / "semantic-input.md"
        semantic_body = (
            (self.asset_root / "AGENTS.md").read_text(encoding="utf-8")
            + "\n# Existing project rules\n\nKeep this.\n"
        ).encode("utf-8")
        semantic_path.write_bytes(semantic_body)

        resolved = resolve_conflicts(
            original,
            (
                ConflictResolution(
                    action_id=conflict.action_id,
                    choice=ConflictChoice.SEMANTIC_MERGE,
                    rendered_path=str(semantic_path),
                    rendered_sha256=hashlib.sha256(semantic_body).hexdigest(),
                ),
            ),
            artifacts,
        )

        self.assertFalse(resolved.conflicts)
        self.assertEqual(
            {
                action.target_path
                for action in resolved.actions
                if action.kind in {ActionKind.CREATE, ActionKind.MERGE}
            },
            {*MANAGED_PATHS, "norn-governance/.norn.json"},
        )

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

    def test_explicit_tree_reports_target_parent_collision_during_analysis(
        self,
    ) -> None:
        """防止嵌套目标父路径为文件时生成表面可执行、实际必失败的计划。"""
        target = self.copy_current_template()
        self.write(target, "docs/appendix/diagrams/flow.md", "# Flow\n")
        self.write(
            target,
            "norn-governance/appendix/diagrams",
            "this path blocks the destination directory\n",
        )

        plan = analyze_governance(
            target,
            self.artifacts(),
            legacy_content_scopes=("appendix",),
        )

        action = self.action_for(
            plan,
            "norn-governance/appendix/diagrams/flow.md",
        )
        self.assertEqual(action.kind, ActionKind.CONFLICT)
        self.assertIn("parent", action.reason)
        self.assertFalse(action.allowed_resolutions)

    def test_explicit_tree_does_not_overwrite_different_project_content(self) -> None:
        target = self.copy_current_template()
        self.write(target, "docs/appendix/guide.md", "legacy guide\n")
        self.write(
            target,
            "norn-governance/appendix/guide.md",
            "current guide\n",
        )

        plan = analyze_governance(
            target,
            self.artifacts(),
            legacy_content_scopes=("appendix",),
        )

        action = self.action_for(plan, "norn-governance/appendix/guide.md")
        self.assertEqual(action.kind, ActionKind.CONFLICT)
        self.assertEqual(
            action.allowed_resolutions,
            (ConflictChoice.SEMANTIC_MERGE,),
        )
        self.assertEqual(
            (target / "norn-governance/appendix/guide.md").read_text(
                encoding="utf-8"
            ),
            "current guide\n",
        )

    def test_explicit_tree_blocks_symlinked_source(self) -> None:
        target = self.copy_current_template()
        outside = self.workspace / "outside-appendix.md"
        outside.write_text("outside\n", encoding="utf-8")
        source = target / "docs/appendix/external.md"
        source.parent.mkdir(parents=True)
        source.symlink_to(outside)

        plan = analyze_governance(
            target,
            self.artifacts(),
            legacy_content_scopes=("appendix",),
        )

        action = self.action_for(plan, "norn-governance/appendix/external.md")
        self.assertEqual(action.kind, ActionKind.CONFLICT)
        self.assertIn("unsupported filesystem type", action.reason)
        self.assertFalse(action.allowed_resolutions)

    def test_explicit_empty_legacy_tree_is_reported_as_mixed_cleanup(self) -> None:
        """防止只剩空旧目录时把删除计划误报为 current 无变更。"""
        target = self.copy_current_template()
        (target / "docs/appendix").mkdir(parents=True)

        plan = analyze_governance(
            target,
            self.artifacts(),
            legacy_content_scopes=("appendix",),
        )

        self.assertEqual(plan.project_state, ProjectState.MIXED)
        self.action_for(plan, "docs/appendix", ActionKind.DELETE)
        self.action_for(plan, "docs", ActionKind.DELETE)

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

    def test_unmodified_managed_block_upgrades_and_preserves_project_text(self) -> None:
        target = self.copy_versioned_project()
        self.append(target, "AGENTS.md", "\n## Project Rule\nKeep this.\n")
        artifacts = self.artifacts()

        plan = analyze_governance(target, artifacts)

        self.assertEqual(plan.project_state, ProjectState.UPGRADEABLE)
        root_action = self.action_for(plan, "AGENTS.md", ActionKind.MERGE)
        rendered = self.rendered_text(artifacts, root_action)
        self.assertIn("## Project Rule\nKeep this.", rendered)
        self.assertIn("## 整体性与变更边界", rendered)
        manifest_action = self.action_for(
            plan, "norn-governance/.norn.json", ActionKind.MERGE
        )
        upgraded_manifest = NornManifest.from_dict(
            json.loads(self.rendered_text(artifacts, manifest_action))
        )
        self.assertEqual(upgraded_manifest.template_version, 1)

    def test_modified_managed_block_requires_explicit_choice(self) -> None:
        target = self.copy_versioned_project()
        root_path = target / "AGENTS.md"
        customized = (
            "<!-- norn:managed:start core-governance -->\n"
            "project customized managed text\n"
            "<!-- norn:managed:end core-governance -->"
        )
        root_path.write_text(
            replace_managed_block(
                root_path.read_text(encoding="utf-8"),
                "core-governance",
                customized,
            ),
            encoding="utf-8",
        )

        plan = analyze_governance(target, self.artifacts())

        root_action = self.action_for(plan, "AGENTS.md", ActionKind.CONFLICT)
        self.assertIn("managed block differs from recorded base", root_action.reason)
        self.assertEqual(
            root_action.allowed_resolutions,
            (
                ConflictChoice.KEEP_CURRENT,
                ConflictChoice.ADOPT_TEMPLATE,
                ConflictChoice.SEMANTIC_MERGE,
            ),
        )

    def test_keep_current_resolves_upgrade_and_records_new_baseline(self) -> None:
        target = self.copy_versioned_project()
        root_path = target / "AGENTS.md"
        customized = (
            "<!-- norn:managed:start core-governance -->\ncustom baseline\n"
            "<!-- norn:managed:end core-governance -->"
        )
        root_path.write_text(
            replace_managed_block(
                root_path.read_text(encoding="utf-8"),
                "core-governance",
                customized,
            ),
            encoding="utf-8",
        )
        artifacts = self.artifacts()
        original = analyze_governance(target, artifacts)
        conflict = self.action_for(original, "AGENTS.md", ActionKind.CONFLICT)

        resolved = resolve_conflicts(
            original,
            (
                ConflictResolution(
                    action_id=conflict.action_id,
                    choice=ConflictChoice.KEEP_CURRENT,
                ),
            ),
            artifacts,
        )

        self.assertNotEqual(resolved.plan_sha256, original.plan_sha256)
        self.assertFalse(resolved.conflicts)
        self.action_for(resolved, "AGENTS.md", ActionKind.KEEP)
        manifest_action = self.action_for(
            resolved, "norn-governance/.norn.json", ActionKind.MERGE
        )
        manifest = NornManifest.from_dict(
            json.loads(self.rendered_text(artifacts, manifest_action))
        )
        self.assertEqual(
            manifest.managed_files["AGENTS.md"].base_sha256,
            parse_managed_blocks(root_path.read_text(encoding="utf-8"))[
                "core-governance"
            ].sha256,
        )

    def test_adopt_template_resolves_customized_legacy_governance(self) -> None:
        target = self.copy_legacy_template()
        self.append(target, "docs/AGENTS.md", "\n## Custom Legacy Rule\n")
        artifacts = self.artifacts()
        original = analyze_governance(target, artifacts)
        conflict = self.action_for(
            original, "norn-governance/AGENTS.md", ActionKind.CONFLICT
        )

        resolved = resolve_conflicts(
            original,
            (
                ConflictResolution(
                    action_id=conflict.action_id,
                    choice=ConflictChoice.ADOPT_TEMPLATE,
                ),
            ),
            artifacts,
        )

        adopted = self.action_for(
            resolved, "norn-governance/AGENTS.md", ActionKind.MERGE
        )
        self.assertEqual(
            self.rendered_text(artifacts, adopted).encode("utf-8"),
            (self.asset_root / "norn-governance/AGENTS.md").read_bytes(),
        )
        self.action_for(resolved, "norn-governance/.norn.json")

    def test_semantic_merge_is_canonicalized_and_hash_bound(self) -> None:
        target = self.copy_legacy_template()
        self.append(target, "docs/AGENTS.md", "\n## Custom Legacy Rule\nKeep this.\n")
        artifacts = self.artifacts()
        original = analyze_governance(target, artifacts)
        conflict = self.action_for(
            original, "norn-governance/AGENTS.md", ActionKind.CONFLICT
        )
        semantic_path = artifacts / "semantic-input.md"
        semantic_body = (
            (self.asset_root / "norn-governance/AGENTS.md").read_text(
                encoding="utf-8"
            )
            + "\n## Custom Legacy Rule\nKeep this.\n"
        ).encode("utf-8")
        semantic_path.write_bytes(semantic_body)
        semantic_sha256 = hashlib.sha256(semantic_body).hexdigest()

        resolved = resolve_conflicts(
            original,
            (
                ConflictResolution(
                    action_id=conflict.action_id,
                    choice=ConflictChoice.SEMANTIC_MERGE,
                    rendered_path=str(semantic_path),
                    rendered_sha256=semantic_sha256,
                ),
            ),
            artifacts,
        )

        action = self.action_for(
            resolved, "norn-governance/AGENTS.md", ActionKind.MERGE
        )
        self.assertEqual(action.output_sha256, semantic_sha256)
        self.assertEqual(
            (artifacts / "rendered" / f"{action.action_id}.content").read_bytes(),
            semantic_body,
        )

    def test_semantic_merge_rejects_outside_or_mismatched_artifact(self) -> None:
        target = self.copy_legacy_template()
        self.append(target, "docs/AGENTS.md", "\n## Custom Legacy Rule\n")
        artifacts = self.artifacts()
        original = analyze_governance(target, artifacts)
        conflict = self.action_for(
            original, "norn-governance/AGENTS.md", ActionKind.CONFLICT
        )
        outside = self.workspace / "outside.md"
        outside.write_text("unsafe\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "artifact root"):
            resolve_conflicts(
                original,
                (
                    ConflictResolution(
                        action_id=conflict.action_id,
                        choice=ConflictChoice.SEMANTIC_MERGE,
                        rendered_path=str(outside),
                        rendered_sha256=hashlib.sha256(b"unsafe\n").hexdigest(),
                    ),
                ),
                artifacts,
            )


if __name__ == "__main__":
    unittest.main()
