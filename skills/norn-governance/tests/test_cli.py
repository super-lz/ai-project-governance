from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "manage_norn_governance.py"
EXPECTED_FILES = [
    "AGENTS.md",
    "norn-governance/.norn.json",
    "norn-governance/AGENTS.md",
    "norn-governance/spec/AGENTS.md",
    "norn-governance/spec/main-spec.md",
    "norn-governance/appendix/README.md",
]
LEGACY_TARGET_FILES = [
    "norn-governance/AGENTS.md",
    "norn-governance/spec/AGENTS.md",
    "norn-governance/spec/main-spec.md",
    "norn-governance/appendix/README.md",
]
LEGACY_FILES = [
    "docs/AGENTS.md",
    "docs/spec/AGENTS.md",
    "docs/spec/main-spec.md",
    "docs/appendix/README.md",
]


class NornGovernanceTests(unittest.TestCase):
    def run_script(self, target: Path, *arguments: str) -> dict:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--target",
                str(target),
                "--report-json",
                *arguments,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def test_apply_creates_only_norn_governance_files(self) -> None:
        """防止初始化器继续把治理文件写进目标项目的 docs/。"""
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)

            dry_run = self.run_script(target)
            self.assertEqual(dry_run["counts"], {"missing": 6, "same": 0, "conflict": 0})
            self.assertEqual([item["path"] for item in dry_run["files"]], EXPECTED_FILES)

            applied = self.run_script(target, "--apply")
            self.assertEqual(applied["written"], EXPECTED_FILES)
            for relative_path in EXPECTED_FILES:
                self.assertTrue((target / relative_path).is_file(), relative_path)
            self.assertFalse((target / "docs").exists())
            self.assertFalse((target / "norn-governance" / "plans").exists())
            manifest = json.loads(
                (target / "norn-governance/.norn.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["template_version"], 1)
            self.assertEqual(
                manifest["managed_files"]["norn-governance/spec/main-spec.md"][
                    "ownership"
                ],
                "project",
            )
            self.assertNotIn(
                "norn:managed",
                (target / "norn-governance/spec/main-spec.md").read_text(
                    encoding="utf-8"
                ),
            )

            repeated = self.run_script(target)
            self.assertEqual(repeated["counts"], {"missing": 0, "same": 6, "conflict": 0})

    def test_apply_does_not_create_duplicate_governance_beside_legacy_files(self) -> None:
        """防止旧版 docs/ 治理文件和新 Norn 规格同时成为事实源。"""
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            for relative_path in LEGACY_FILES:
                legacy_file = target / relative_path
                legacy_file.parent.mkdir(parents=True, exist_ok=True)
                legacy_file.write_text(f"# legacy {relative_path}\n", encoding="utf-8")

            report = self.run_script(target, "--apply")
            results = {item["path"]: item for item in report["files"]}

            self.assertEqual(report["counts"], {"missing": 1, "same": 0, "conflict": 5})
            self.assertEqual(report["written"], ["AGENTS.md"])
            self.assertEqual(results["norn-governance/.norn.json"]["status"], "conflict")
            self.assertFalse((target / "norn-governance/.norn.json").exists())
            for new_path, legacy_path in zip(LEGACY_TARGET_FILES, LEGACY_FILES, strict=True):
                self.assertEqual(results[new_path]["status"], "conflict")
                self.assertEqual(results[new_path]["action"], "skip")
                self.assertEqual(results[new_path]["legacy_path"], legacy_path)
                self.assertFalse((target / new_path).exists())
            self.assertFalse((target / "norn-governance").exists())

    def test_legacy_paths_remain_conflicts_when_norn_files_exist(self) -> None:
        """防止新旧治理路径并存时，初始化器把双规格源误报为正常。"""
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            self.run_script(target, "--apply")
            for relative_path in LEGACY_FILES:
                legacy_file = target / relative_path
                legacy_file.parent.mkdir(parents=True, exist_ok=True)
                legacy_file.write_text(f"# legacy {relative_path}\n", encoding="utf-8")

            report = self.run_script(target)
            results = {item["path"]: item for item in report["files"]}

            self.assertEqual(report["counts"], {"missing": 0, "same": 2, "conflict": 4})
            for new_path, legacy_path in zip(LEGACY_TARGET_FILES, LEGACY_FILES, strict=True):
                self.assertEqual(results[new_path]["status"], "conflict")
                self.assertEqual(results[new_path]["legacy_path"], legacy_path)


if __name__ == "__main__":
    unittest.main()
