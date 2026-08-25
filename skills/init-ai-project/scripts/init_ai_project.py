#!/usr/bin/env python3
"""从本 skill 的内置模板初始化 AI 项目治理文件。"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


TEMPLATE_FILES = [
    "AGENTS.md",
    "norn-governance/AGENTS.md",
    "norn-governance/spec/AGENTS.md",
    "norn-governance/spec/main-spec.md",
    "norn-governance/appendix/README.md",
]

LEGACY_PATHS = {
    "norn-governance/AGENTS.md": "docs/AGENTS.md",
    "norn-governance/spec/AGENTS.md": "docs/spec/AGENTS.md",
    "norn-governance/spec/main-spec.md": "docs/spec/main-spec.md",
    "norn-governance/appendix/README.md": "docs/appendix/README.md",
}


@dataclass(frozen=True)
class FileResult:
    path: str
    status: str
    action: str
    legacy_path: str | None = None
    fusion_guidance: str | None = None
    template_headings: list[str] | None = None
    target_headings: list[str] | None = None

    def to_dict(self) -> dict:
        payload: dict = {
            "path": self.path,
            "status": self.status,
            "action": self.action,
        }
        if self.fusion_guidance:
            payload["fusion_guidance"] = self.fusion_guidance
        if self.legacy_path:
            payload["legacy_path"] = self.legacy_path
        if self.template_headings is not None:
            payload["template_headings"] = self.template_headings
        if self.target_headings is not None:
            payload["target_headings"] = self.target_headings
        return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="分析或初始化 AI 项目治理文件。"
    )
    parser.add_argument(
        "--target",
        required=True,
        help="要分析或初始化的目标仓库根目录。",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="复制缺失文件。已有文件永远不会被覆盖。",
    )
    parser.add_argument(
        "--report-json",
        action="store_true",
        help="只输出 JSON 报告。",
    )
    return parser.parse_args()


def template_root() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "ai-project-governance-template"


def guidance_for(path: str) -> str:
    if path == "AGENTS.md":
        return (
            "用户确认后，将模板中的项目总指挥职责、第一性原则工作流、"
            "实现规格维护规则和文档治理规则融合到现有根目录 AGENTS.md。"
        )
    if path.startswith("norn-governance/spec/"):
        return (
            "保留目标项目已有实现规格内容；用户确认后，融合模板中关于主规格权威性、"
            "规格变更确认和禁止记录开发流水的规则。"
        )
    if path == "norn-governance/AGENTS.md":
        return (
            "保留目标项目已有治理分类；用户确认后，融合模板中 spec/plans/appendix "
            "职责和长期、临时材料的边界。"
        )
    return (
        "除非用户确认融合，否则保留目标文件；只补充附录材料不作为权威实现依据的治理规则。"
    )


def legacy_guidance_for(path: str, legacy_path: str) -> str:
    return (
        f"检测到旧版 Norn 治理路径 {legacy_path}。不要让它与 {path} 形成两套依据；"
        "先分析旧文件是否属于治理模板，再由用户确认迁移，且不要移动目标项目的其他 docs 内容。"
    )


def markdown_headings(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return []
    headings: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        title = stripped.lstrip("#").strip()
        if title:
            headings.append(title)
    return headings


def analyze_file(target_root: Path, source_root: Path, relative_path: str) -> FileResult:
    source = source_root / relative_path
    target = target_root / relative_path

    if not source.is_file():
        raise FileNotFoundError(f"模板文件缺失：{source}")

    legacy_path = LEGACY_PATHS.get(relative_path)
    if legacy_path:
        legacy_target = target_root / legacy_path
        if legacy_target.exists():
            return FileResult(
                path=relative_path,
                status="conflict",
                action="skip",
                legacy_path=legacy_path,
                fusion_guidance=legacy_guidance_for(relative_path, legacy_path),
                template_headings=markdown_headings(source),
                target_headings=(
                    markdown_headings(legacy_target) if legacy_target.is_file() else []
                ),
            )

    if not target.exists():
        return FileResult(
            path=relative_path,
            status="missing",
            action="copy" if target_root.exists() else "none",
        )

    if not target.is_file():
        return FileResult(
            path=relative_path,
            status="conflict",
            action="skip",
            fusion_guidance=f"目标路径存在但不是文件。{guidance_for(relative_path)}",
            template_headings=markdown_headings(source),
            target_headings=[],
        )

    if target.read_bytes() == source.read_bytes():
        return FileResult(path=relative_path, status="same", action="none")

    return FileResult(
        path=relative_path,
        status="conflict",
        action="skip",
        fusion_guidance=guidance_for(relative_path),
        template_headings=markdown_headings(source),
        target_headings=markdown_headings(target),
    )


def copy_missing(target_root: Path, source_root: Path, results: list[FileResult]) -> list[str]:
    written: list[str] = []
    for result in results:
        if result.status != "missing":
            continue
        source = source_root / result.path
        target = target_root / result.path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        written.append(result.path)
    return written


def build_report(target_root: Path, apply: bool, results: list[FileResult], written: list[str]) -> dict:
    counts = {"missing": 0, "same": 0, "conflict": 0}
    for result in results:
        counts[result.status] += 1
    return {
        "target": str(target_root),
        "apply": apply,
        "counts": counts,
        "written": written,
        "files": [result.to_dict() for result in results],
    }


def print_human_report(report: dict) -> None:
    mode = "apply" if report["apply"] else "dry-run"
    print(f"AI 项目治理初始化报告（{mode}）")
    print(f"目标目录：{report['target']}")
    print(
        "统计："
        f"missing={report['counts']['missing']}, "
        f"same={report['counts']['same']}, "
        f"conflict={report['counts']['conflict']}"
    )

    if report["written"]:
        print("\n已写入文件：")
        for path in report["written"]:
            print(f"  - {path}")

    print("\n文件结果：")
    for item in report["files"]:
        print(f"  - {item['path']}: {item['status']} ({item['action']})")
        if "target_headings" in item:
            target_headings = ", ".join(item["target_headings"]) or "（无）"
            template_headings = ", ".join(item["template_headings"]) or "（无）"
            print(f"    目标标题：{target_headings}")
            print(f"    模板标题：{template_headings}")
        if "legacy_path" in item:
            print(f"    旧版路径：{item['legacy_path']}")
        if "fusion_guidance" in item:
            print(f"    融合建议：{item['fusion_guidance']}")

    if report["counts"]["conflict"]:
        print(
            "\n检测到冲突，已跳过覆盖。编辑已有治理文件前，先查看融合建议并询问用户。"
        )
    elif not report["apply"]:
        print("\n当前只是 dry-run。需要复制缺失文件时，请重新执行并加上 --apply。")


def main() -> int:
    args = parse_args()
    target_root = Path(args.target).expanduser().resolve()
    source_root = template_root()

    if not target_root.exists():
        print(f"目标路径不存在：{target_root}", file=sys.stderr)
        return 2
    if not target_root.is_dir():
        print(f"目标路径不是目录：{target_root}", file=sys.stderr)
        return 2
    if not source_root.is_dir():
        print(f"模板目录不存在：{source_root}", file=sys.stderr)
        return 2

    try:
        results = [analyze_file(target_root, source_root, path) for path in TEMPLATE_FILES]
        written = copy_missing(target_root, source_root, results) if args.apply else []
    except OSError as exc:
        print(f"初始化失败：{exc}", file=sys.stderr)
        return 1

    report = build_report(target_root, args.apply, results, written)
    if args.report_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
