from __future__ import annotations

import json
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

    def test_conflict_action_requires_explicit_allowed_choices(self) -> None:
        action = self.make_conflict_action()

        self.assertEqual(
            action.allowed_resolutions,
            (ConflictChoice.ADOPT_TEMPLATE, ConflictChoice.SEMANTIC_MERGE),
        )

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


if __name__ == "__main__":
    unittest.main()
