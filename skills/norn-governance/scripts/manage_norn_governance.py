#!/usr/bin/env python3
"""Norn Governance 的确定性分析、冲突解析和执行入口。"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from norn_governance.analyzer import (
    analyze_governance,
    normalize_legacy_content_scopes,
    resolve_conflicts,
)
from norn_governance.executor import ApplyResult, apply_plan
from norn_governance.models import (
    ActionKind,
    ConflictResolution,
    GovernancePlan,
    load_plan,
    write_plan,
)


BRAND = "Norn Governance"


def _add_common_report_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--report-json",
        action="store_true",
        help="输出机器可读 JSON 报告。",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"{BRAND}：安全初始化、迁移或升级项目 AI 协作治理。"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    analyze = commands.add_parser(
        "analyze",
        help="只读分析项目状态并生成带指纹的临时执行计划。",
    )
    analyze.add_argument("--target", required=True, help="目标仓库根目录。")
    analyze.add_argument(
        "--artifact-dir",
        help="机器计划和渲染产物目录；必须位于目标仓库之外。",
    )
    analyze.add_argument(
        "--include-legacy-tree",
        action="append",
        choices=("appendix", "spec", "all"),
        default=[],
        help="经用户明确授权后，递归迁移指定旧治理目录；可重复传入。",
    )
    _add_common_report_argument(analyze)

    resolve = commands.add_parser(
        "resolve",
        help="将明确的冲突选择绑定到已有计划。",
    )
    resolve.add_argument("--target", required=True, help="目标仓库根目录。")
    resolve.add_argument("--plan", required=True, help="待解析的 plan.json。")
    resolve.add_argument(
        "--resolutions",
        required=True,
        help="包含 resolutions 数组的 JSON 文件。",
    )
    _add_common_report_argument(resolve)

    apply = commands.add_parser(
        "apply",
        help="重新验证计划、项目指纹和渲染产物后执行。",
    )
    apply.add_argument("--target", required=True, help="目标仓库根目录。")
    apply.add_argument("--plan", required=True, help="已确认且无冲突的 plan.json。")
    _add_common_report_argument(apply)
    return parser.parse_args()


def _canonical_target(raw_target: str) -> Path:
    target = Path(raw_target).expanduser().resolve()
    if not target.exists():
        raise ValueError(f"target does not exist: {target}")
    if not target.is_dir():
        raise ValueError(f"target is not a directory: {target}")
    return target


def _require_plan_target(plan: GovernancePlan, target: Path) -> None:
    if Path(plan.target_root) != target:
        raise ValueError(
            f"target does not match plan: target={target}, plan={plan.target_root}"
        )


def _plan_sections(plan: GovernancePlan) -> dict[str, list[dict[str, Any]]]:
    ownership_evidence: list[dict[str, Any]] = []
    relocations: list[dict[str, Any]] = []
    rule_upgrades: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    deletions: list[dict[str, Any]] = []
    risks: list[dict[str, Any]] = []
    verification: list[dict[str, Any]] = []

    for action in plan.actions:
        ownership_evidence.append(
            {
                "action_id": action.action_id,
                "target_path": action.target_path,
                "ownership": action.ownership.value,
                "evidence": list(action.evidence),
            }
        )
        if action.source_path is not None:
            relocations.append(
                {
                    "action_id": action.action_id,
                    "source_path": action.source_path,
                    "target_path": action.target_path,
                    "kind": action.kind.value,
                }
            )
            deletions.append(
                {
                    "action_id": action.action_id,
                    "path": action.source_path,
                    "condition": "canonical target is written and verified",
                }
            )
        if action.kind in {ActionKind.CREATE, ActionKind.MERGE, ActionKind.MOVE}:
            rule_upgrades.append(
                {
                    "action_id": action.action_id,
                    "target_path": action.target_path,
                    "kind": action.kind.value,
                    "reason": action.reason,
                }
            )
        if action.kind is ActionKind.CONFLICT:
            conflicts.append(
                {
                    "action_id": action.action_id,
                    "target_path": action.target_path,
                    "reason": action.reason,
                    "allowed_resolutions": [
                        choice.value for choice in action.allowed_resolutions
                    ],
                }
            )
        if action.kind is ActionKind.DELETE:
            deletions.append(
                {
                    "action_id": action.action_id,
                    "path": action.target_path,
                    "condition": action.reason,
                }
            )
        if action.kind is not ActionKind.KEEP:
            risks.append(
                {
                    "action_id": action.action_id,
                    "target_path": action.target_path,
                    "risk": action.risk,
                }
            )
        verification.append(
            {
                "action_id": action.action_id,
                "target_path": action.target_path,
                "checks": list(action.verification),
            }
        )

    return {
        "ownership_evidence": ownership_evidence,
        "relocations": relocations,
        "rule_upgrades": rule_upgrades,
        "conflicts": conflicts,
        "deletions": deletions,
        "risks": risks,
        "verification": verification,
    }


def _plan_report(
    command: str,
    plan: GovernancePlan,
    plan_path: Path,
    legacy_content_scopes: tuple[str, ...] = (),
) -> dict[str, Any]:
    action_counts = Counter(action.kind.value for action in plan.actions)
    return {
        "brand": BRAND,
        "command": command,
        "target": plan.target_root,
        "project_state": plan.project_state.value,
        "template_version": plan.template_version,
        "legacy_content_scopes": list(legacy_content_scopes),
        "plan_path": str(plan_path),
        "plan_sha256": plan.plan_sha256,
        "executable": not plan.conflicts
        and all(action.kind is not ActionKind.CONFLICT for action in plan.actions),
        "summary": {
            "total_actions": len(plan.actions),
            "action_counts": dict(sorted(action_counts.items())),
        },
        "actions": [action.to_dict() for action in plan.actions],
        "sections": _plan_sections(plan),
    }


def _verification_dict(result: ApplyResult) -> dict[str, Any]:
    verification = result.verification
    return {
        "state": verification.state.value,
        "manifest_valid": verification.manifest_valid,
        "single_spec_source": verification.single_spec_source,
        "checked_paths": list(verification.checked_paths),
        "warnings": list(verification.warnings),
    }


def _apply_report(target: Path, plan_path: Path, result: ApplyResult) -> dict[str, Any]:
    return {
        "brand": BRAND,
        "command": "apply",
        "target": str(target),
        "plan_path": str(plan_path),
        "created": list(result.created),
        "updated": list(result.updated),
        "removed": list(result.removed),
        "removed_directories": list(result.removed_directories),
        "verification": _verification_dict(result),
    }


def _load_resolutions(path: Path) -> tuple[ConflictResolution, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid resolutions file: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("resolutions file must be an object")
    raw_resolutions = payload.get("resolutions")
    if not isinstance(raw_resolutions, list):
        raise ValueError("resolutions must be an array")
    resolutions: list[ConflictResolution] = []
    for index, raw_resolution in enumerate(raw_resolutions):
        if not isinstance(raw_resolution, Mapping):
            raise ValueError(f"resolutions[{index}] must be an object")
        resolutions.append(ConflictResolution.from_dict(raw_resolution))
    return tuple(resolutions)


def _print_items(items: list[dict[str, Any]], formatter) -> None:
    if not items:
        print("  - 无")
        return
    for item in items:
        print(f"  - {formatter(item)}")


def print_human_plan_report(report: Mapping[str, Any]) -> None:
    sections = report["sections"]
    print(f"{BRAND} 分析报告")
    print(f"目标：{report['target']}")
    print(f"计划：{report['plan_path']}")
    if report["legacy_content_scopes"]:
        print("显式旧目录范围：" + "、".join(report["legacy_content_scopes"]))
    print("\n状态")
    print(
        f"  - {report['project_state']}；"
        f"{'可执行' if report['executable'] else '需要先解决冲突'}"
    )
    print("\n归属证据")
    _print_items(
        sections["ownership_evidence"],
        lambda item: (
            f"{item['target_path']} [{item['ownership']}]："
            + "；".join(item["evidence"])
        ),
    )
    print("\n路径迁移")
    _print_items(
        sections["relocations"],
        lambda item: f"{item['source_path']} -> {item['target_path']} ({item['kind']})",
    )
    print("\n规则升级")
    _print_items(
        sections["rule_upgrades"],
        lambda item: f"{item['target_path']} ({item['kind']})：{item['reason']}",
    )
    print("\n冲突")
    _print_items(
        sections["conflicts"],
        lambda item: (
            f"{item['target_path']}：{item['reason']}；"
            f"可选={','.join(item['allowed_resolutions']) or '需外部修正后重析'}"
        ),
    )
    print("\n删除")
    _print_items(
        sections["deletions"],
        lambda item: f"{item['path']}：{item['condition']}",
    )
    print("\n风险")
    _print_items(
        sections["risks"],
        lambda item: f"{item['target_path']}：{item['risk']}",
    )
    print("\n验证")
    _print_items(
        sections["verification"],
        lambda item: f"{item['target_path']}：{'；'.join(item['checks'])}",
    )


def print_human_apply_report(report: Mapping[str, Any]) -> None:
    print(f"{BRAND} 执行报告")
    print(f"目标：{report['target']}")
    for heading, key in (
        ("已创建", "created"),
        ("已更新", "updated"),
        ("已删除文件", "removed"),
        ("已删除空目录", "removed_directories"),
    ):
        print(f"\n{heading}")
        values = report[key]
        if values:
            for value in values:
                print(f"  - {value}")
        else:
            print("  - 无")
    verification = report["verification"]
    print("\n验证")
    print(f"  - 状态：{verification['state']}")
    print(f"  - manifest 有效：{verification['manifest_valid']}")
    print(f"  - 单一规格源：{verification['single_spec_source']}")
    for warning in verification["warnings"]:
        print(f"  - 警告：{warning}")


def _emit(report: Mapping[str, Any], report_json: bool) -> None:
    if report_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    elif report["command"] == "apply":
        print_human_apply_report(report)
    else:
        print_human_plan_report(report)


def _run_analyze(args: argparse.Namespace, target: Path) -> dict[str, Any]:
    artifact_root = (
        Path(args.artifact_dir).expanduser().resolve()
        if args.artifact_dir
        else Path(tempfile.mkdtemp(prefix="norn-governance-"))
    )
    legacy_content_scopes = normalize_legacy_content_scopes(
        args.include_legacy_tree
    )
    plan = analyze_governance(
        target,
        artifact_root,
        legacy_content_scopes=legacy_content_scopes,
    )
    return _plan_report(
        "analyze",
        plan,
        artifact_root / "plan.json",
        legacy_content_scopes,
    )


def _run_resolve(args: argparse.Namespace, target: Path) -> dict[str, Any]:
    plan_path = Path(args.plan).expanduser().resolve()
    plan = load_plan(plan_path)
    _require_plan_target(plan, target)
    resolutions = _load_resolutions(Path(args.resolutions).expanduser().resolve())
    resolved = resolve_conflicts(plan, resolutions, plan_path.parent)
    resolved_path = write_plan(resolved, plan_path.parent)
    return _plan_report("resolve", resolved, resolved_path)


def _run_apply(args: argparse.Namespace, target: Path) -> dict[str, Any]:
    plan_path = Path(args.plan).expanduser().resolve()
    plan = load_plan(plan_path)
    _require_plan_target(plan, target)
    result = apply_plan(plan_path)
    return _apply_report(target, plan_path, result)


def main() -> int:
    args = parse_args()
    try:
        target = _canonical_target(args.target)
        if args.command == "analyze":
            report = _run_analyze(args, target)
        elif args.command == "resolve":
            report = _run_resolve(args, target)
        else:
            report = _run_apply(args, target)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"{BRAND} 失败：{exc}", file=sys.stderr)
        return 1
    _emit(report, args.report_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
