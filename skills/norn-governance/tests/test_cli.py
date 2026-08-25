from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "manage_norn_governance.py"
LEGACY_TEMPLATE = SKILL_ROOT / "assets" / "legacy-templates" / "0"
EXPECTED_FILES = {
    "AGENTS.md",
    "norn-governance/.norn.json",
    "norn-governance/AGENTS.md",
    "norn-governance/spec/AGENTS.md",
    "norn-governance/spec/main-spec.md",
    "norn-governance/appendix/README.md",
}


class NornGovernanceCliTests(unittest.TestCase):
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

    def copy_legacy_template(self) -> Path:
        target = self.make_target()
        shutil.copytree(LEGACY_TEMPLATE, target, dirs_exist_ok=True)
        return target

    def run_cli_raw(self, *arguments: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *(str(value) for value in arguments)],
            check=False,
            capture_output=True,
            text=True,
        )

    def run_cli_json(self, *arguments: object) -> dict:
        completed = self.run_cli_raw(*arguments, "--report-json")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def analyze(self, target: Path, artifacts: Path | None = None) -> dict:
        artifacts = artifacts or self.workspace / f"artifacts-{self.counter}"
        return self.run_cli_json(
            "analyze",
            "--target",
            target,
            "--artifact-dir",
            artifacts,
        )

    def test_analyze_empty_project_writes_plan_but_not_project_files(self) -> None:
        target = self.make_target()
        before = tuple(target.rglob("*"))

        report = self.analyze(target)

        self.assertEqual(report["command"], "analyze")
        self.assertEqual(report["project_state"], "uninitialized")
        self.assertTrue(report["executable"])
        self.assertTrue(Path(report["plan_path"]).is_file())
        self.assertEqual(tuple(target.rglob("*")), before)
        self.assertEqual(
            {action["target_path"] for action in report["actions"]},
            EXPECTED_FILES,
        )

    def test_analyze_legacy_project_reports_relocations_without_writes(self) -> None:
        target = self.copy_legacy_template()
        before = {
            path.relative_to(target).as_posix(): path.read_bytes()
            for path in target.rglob("*")
            if path.is_file()
        }

        report = self.analyze(target)

        self.assertEqual(report["project_state"], "legacy")
        self.assertEqual(
            {
                action["source_path"]
                for action in report["actions"]
                if action["source_path"]
            },
            {
                "docs/AGENTS.md",
                "docs/spec/AGENTS.md",
                "docs/spec/main-spec.md",
                "docs/appendix/README.md",
            },
        )
        self.assertTrue(report["sections"]["relocations"])
        after = {
            path.relative_to(target).as_posix(): path.read_bytes()
            for path in target.rglob("*")
            if path.is_file()
        }
        self.assertEqual(after, before)

    def test_apply_requires_plan_artifact(self) -> None:
        target = self.make_target()

        completed = self.run_cli_raw("apply", "--target", target)

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--plan", completed.stderr)

    def test_analyze_then_apply_initializes_and_verifies_project(self) -> None:
        target = self.make_target()
        analysis = self.analyze(target)

        applied = self.run_cli_json(
            "apply",
            "--target",
            target,
            "--plan",
            analysis["plan_path"],
        )

        self.assertEqual(applied["command"], "apply")
        self.assertEqual(applied["verification"]["state"], "current")
        self.assertTrue(applied["verification"]["manifest_valid"])
        self.assertTrue(applied["verification"]["single_spec_source"])
        self.assertEqual(set(applied["created"]), EXPECTED_FILES)
        self.assertFalse((target / "docs").exists())
        self.assertFalse((target / "norn-governance/plans").exists())

    def test_apply_rejects_tampered_plan_digest(self) -> None:
        target = self.make_target()
        analysis = self.analyze(target)
        plan_path = Path(analysis["plan_path"])
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
        payload["target_root"] = str(self.make_target())
        plan_path.write_text(json.dumps(payload), encoding="utf-8")

        completed = self.run_cli_raw(
            "apply", "--target", target, "--plan", plan_path
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("plan digest mismatch", completed.stderr)

    def test_apply_rejects_target_that_differs_from_plan(self) -> None:
        target = self.make_target()
        other_target = self.make_target()
        analysis = self.analyze(target)

        completed = self.run_cli_raw(
            "apply",
            "--target",
            other_target,
            "--plan",
            analysis["plan_path"],
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("target does not match plan", completed.stderr)
        self.assertEqual(tuple(other_target.iterdir()), ())

    def test_human_analysis_contains_decision_sections(self) -> None:
        target = self.copy_legacy_template()
        completed = self.run_cli_raw(
            "analyze",
            "--target",
            target,
            "--artifact-dir",
            self.workspace / "human-artifacts",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        for heading in (
            "状态",
            "归属证据",
            "路径迁移",
            "规则升级",
            "冲突",
            "删除",
            "风险",
            "验证",
        ):
            self.assertIn(heading, completed.stdout)
        self.assertIn("Norn Governance", completed.stdout)

    def test_resolve_adopt_template_rebuilds_executable_plan(self) -> None:
        target = self.copy_legacy_template()
        with (target / "docs/AGENTS.md").open("a", encoding="utf-8") as stream:
            stream.write("\n## Project-specific docs rule\n")
        analysis = self.analyze(target)
        conflict = next(
            action
            for action in analysis["actions"]
            if action["target_path"] == "norn-governance/AGENTS.md"
        )
        resolutions_path = Path(analysis["plan_path"]).parent / "resolutions.json"
        resolutions_path.write_text(
            json.dumps(
                {
                    "resolutions": [
                        {
                            "action_id": conflict["action_id"],
                            "choice": "adopt-template",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        resolved = self.run_cli_json(
            "resolve",
            "--target",
            target,
            "--plan",
            analysis["plan_path"],
            "--resolutions",
            resolutions_path,
        )

        self.assertTrue(resolved["executable"])
        self.assertFalse(resolved["sections"]["conflicts"])
        applied = self.run_cli_json(
            "apply",
            "--target",
            target,
            "--plan",
            resolved["plan_path"],
        )
        self.assertEqual(applied["verification"]["state"], "current")


if __name__ == "__main__":
    unittest.main()
