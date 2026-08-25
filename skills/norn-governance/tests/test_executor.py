from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_ROOT = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from norn_governance.analyzer import analyze_governance  # noqa: E402
import norn_governance.executor as executor_module  # noqa: E402
from norn_governance.executor import (  # noqa: E402
    PlanArtifactError,
    PlanConflictError,
    PlanPreconditionError,
    apply_plan,
)
from norn_governance.models import ActionKind, ProjectState  # noqa: E402
from norn_governance.templates import (  # noqa: E402
    asset_template_root,
    legacy_template_root,
)


class GovernanceExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary_directory.name)
        self.counter = 0

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def make_target(self) -> Path:
        self.counter += 1
        target = self.workspace / f"target-{self.counter}"
        target.mkdir()
        return target

    def artifacts(self) -> Path:
        return self.workspace / f"artifacts-{self.counter}"

    def write(self, target: Path, relative_path: str, text: str) -> None:
        path = target / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def legacy_plan(self) -> tuple[Path, Path]:
        target = self.make_target()
        shutil.copytree(legacy_template_root(), target, dirs_exist_ok=True)
        artifacts = self.artifacts()
        analyze_governance(target, artifacts)
        return target, artifacts / "plan.json"

    def test_apply_rejects_source_changed_after_analysis(self) -> None:
        target, plan_path = self.legacy_plan()
        self.write(target, "docs/spec/main-spec.md", "changed after confirmation\n")

        with self.assertRaisesRegex(PlanPreconditionError, "fingerprint changed"):
            apply_plan(plan_path)

        self.assertTrue((target / "docs/spec/main-spec.md").is_file())
        self.assertFalse((target / "norn-governance/spec/main-spec.md").exists())

    def test_corrupt_rendered_artifact_writes_nothing_and_keeps_sources(self) -> None:
        target, plan_path = self.legacy_plan()
        rendered = next((plan_path.parent / "rendered").glob("*.content"))
        rendered.write_text("corrupted\n", encoding="utf-8")

        with self.assertRaisesRegex(PlanArtifactError, "artifact hash mismatch"):
            apply_plan(plan_path)

        self.assertTrue((target / "docs/AGENTS.md").is_file())
        self.assertTrue((target / "docs/spec/main-spec.md").is_file())
        self.assertFalse((target / "norn-governance/.norn.json").exists())

    def test_unresolved_conflict_is_not_executable(self) -> None:
        target = self.make_target()
        shutil.copytree(legacy_template_root(), target, dirs_exist_ok=True)
        with (target / "docs/AGENTS.md").open("a", encoding="utf-8") as stream:
            stream.write("\n## Custom Rule\n")
        artifacts = self.artifacts()
        analyze_governance(target, artifacts)

        with self.assertRaisesRegex(PlanConflictError, "unresolved conflict"):
            apply_plan(artifacts / "plan.json")

        self.assertFalse((target / "norn-governance").exists())

    def test_parent_symlink_added_after_analysis_is_rejected(self) -> None:
        target, plan_path = self.legacy_plan()
        outside = self.workspace / "outside"
        outside.mkdir()
        (target / "norn-governance").symlink_to(outside, target_is_directory=True)

        with self.assertRaisesRegex(PlanPreconditionError, "symlink"):
            apply_plan(plan_path)

        self.assertTrue((target / "docs/AGENTS.md").exists())
        self.assertEqual(tuple(outside.iterdir()), ())

    def test_mid_write_failure_keeps_every_legacy_source(self) -> None:
        target, plan_path = self.legacy_plan()
        real_replace = __import__("os").replace
        replace_count = 0

        def fail_second_replace(source: str | Path, destination: str | Path) -> None:
            nonlocal replace_count
            replace_count += 1
            if replace_count == 2:
                raise OSError("injected target replace failure")
            real_replace(source, destination)

        with patch(
            "norn_governance.executor.os.replace", side_effect=fail_second_replace
        ):
            with self.assertRaisesRegex(OSError, "injected target replace failure"):
                apply_plan(plan_path)

        for relative_path in (
            "docs/AGENTS.md",
            "docs/spec/AGENTS.md",
            "docs/spec/main-spec.md",
            "docs/appendix/README.md",
        ):
            self.assertTrue((target / relative_path).is_file(), relative_path)
        self.assertFalse((target / "norn-governance/.norn.json").exists())

    def test_source_changed_during_target_writes_is_not_deleted(self) -> None:
        target, plan_path = self.legacy_plan()
        real_atomic_replace = executor_module._atomic_replace_target
        mutated = False

        def replace_then_mutate_source(action, target_root, staged_path) -> None:
            nonlocal mutated
            real_atomic_replace(action, target_root, staged_path)
            if not mutated:
                mutated = True
                self.write(
                    target,
                    "docs/AGENTS.md",
                    (target / "docs/AGENTS.md").read_text(encoding="utf-8")
                    + "\nconcurrent edit\n",
                )

        with patch(
            "norn_governance.executor._atomic_replace_target",
            side_effect=replace_then_mutate_source,
        ):
            with self.assertRaisesRegex(
                PlanPreconditionError, "fingerprint changed before deletion"
            ):
                apply_plan(plan_path)

        self.assertIn(
            "concurrent edit",
            (target / "docs/AGENTS.md").read_text(encoding="utf-8"),
        )
        self.assertFalse((target / "norn-governance/.norn.json").exists())

    def test_complete_migration_preserves_other_docs_and_is_idempotent(self) -> None:
        target, plan_path = self.legacy_plan()
        self.write(target, "docs/architecture.md", "project-owned\n")
        artifacts = plan_path.parent
        analyze_governance(target, artifacts)
        original_spec = (target / "docs/spec/main-spec.md").read_text(
            encoding="utf-8"
        )

        result = apply_plan(plan_path)

        expected_spec = original_spec
        for old, new in {
            "docs/AGENTS.md": "norn-governance/AGENTS.md",
            "docs/spec/AGENTS.md": "norn-governance/spec/AGENTS.md",
            "docs/spec/main-spec.md": "norn-governance/spec/main-spec.md",
            "docs/appendix/README.md": "norn-governance/appendix/README.md",
        }.items():
            expected_spec = expected_spec.replace(old, new)
        self.assertEqual(
            (target / "norn-governance/spec/main-spec.md").read_text(
                encoding="utf-8"
            ),
            expected_spec,
        )
        self.assertEqual(
            (target / "docs/architecture.md").read_text(encoding="utf-8"),
            "project-owned\n",
        )
        self.assertFalse((target / "docs/spec").exists())
        self.assertEqual(result.verification.state, ProjectState.CURRENT)
        second_artifacts = self.workspace / "second-analysis"
        second_plan = analyze_governance(target, second_artifacts)
        self.assertEqual(second_plan.project_state, ProjectState.CURRENT)
        self.assertTrue(
            all(action.kind is ActionKind.KEEP for action in second_plan.actions)
        )

    def test_empty_project_initialization_applies_to_current_state(self) -> None:
        target = self.make_target()
        artifacts = self.artifacts()
        analyze_governance(target, artifacts)

        result = apply_plan(artifacts / "plan.json")

        self.assertEqual(result.verification.state, ProjectState.CURRENT)
        self.assertTrue((target / "norn-governance/.norn.json").is_file())
        self.assertFalse((target / "norn-governance/plans").exists())


if __name__ == "__main__":
    unittest.main()
