# Norn Governance Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将一次性 `init-ai-project` 初始化器升级为唯一 canonical `$norn-governance` skill，使其能够初始化新项目、识别并迁移旧 `docs/` 治理结构、升级已采用 Norn 的项目，同时保留项目内容和其他文档。

**Architecture:** 用户只与 skill 交互；skill 通过确定性 Python 引擎先生成带文件指纹的机器计划，解释后取得一次确认，再按未变化的计划执行。版本化 `.norn.json` 和 Markdown 受管区块负责后续升级；确定性引擎只自动转换已知模板和未修改受管区块，定制旧文档的语义融合由 skill 展示并取得选择后再作为带哈希的产物交给执行器。所有移动和删除都晚于目标内容校验。

**Tech Stack:** Python 3 标准库、Markdown、JSON、SHA-256、`unittest`、Git。

**Spec:** `norn-governance/spec/main-spec.md`

## Global Constraints

- Canonical 名称硬切换为 `norn-governance`、`$norn-governance` 和 `manage_norn_governance.py`，不保留 `init-ai-project` 别名或旧脚本入口。
- 用户只与 skill 交互；内部命令不转嫁给用户。
- 所有写入、移动和删除先 dry-run、后取得用户确认；执行前重新验证全部文件指纹。
- 只迁移确认属于 Norn 的四个旧治理文件，绝不整体移动或重命名项目 `docs/`。
- `norn-governance/spec/main-spec.md` 初始化后归项目所有，升级不得用模板覆盖。
- 新路径内容冲突、受管区块被修改或归属不明确时，必须报告并等待选择，不静默覆盖。
- 确定性脚本不得猜测式融合任意 Markdown；只有已知旧模板、精确路径引用和未修改受管区块可以自动转换。
- 旧源文件在目标内容写入并校验成功前不得删除；旧目录仅在完全为空时删除。
- `norn-governance/plans/` 仍按需创建，不进入固定初始化清单；跨会话或跨设备恢复计划只保存意图、状态、路径、风险和重新分析指引，不保存文件正文或临时产物路径，完成或取消后删除。
- Skill 不自动提交、推送、创建分支或修改 Git 配置。
- 只使用 Python 标准库，不增加第三方运行时依赖。
- 本次只实现 Norn AI 治理生命周期，不加入 Flutter 项目初始化或其他项目脚手架能力。
- 仓库模板与 skill 资产必须逐文件一致；本机安装仅在仓库版本通过全部验证后同步。

---

## Target File Structure

```text
README.md
template/
  AGENTS.md
  norn-governance/
    .norn.json
    AGENTS.md
    spec/
      AGENTS.md
      main-spec.md
    appendix/
      README.md
skills/
  norn-governance/
    SKILL.md
    agents/
      openai.yaml
    references/
      recovery-plans.md
    assets/
      ai-project-governance-template/
        AGENTS.md
        norn-governance/
          .norn.json
          AGENTS.md
          spec/
            AGENTS.md
            main-spec.md
          appendix/
            README.md
      legacy-templates/
        0/
          AGENTS.md
          docs/
            AGENTS.md
            spec/
              AGENTS.md
              main-spec.md
            appendix/
              README.md
    scripts/
      manage_norn_governance.py
      norn_governance/
        __init__.py
        analyzer.py
        executor.py
        managed_markdown.py
        models.py
        templates.py
    tests/
      test_analyzer.py
      test_cli.py
      test_executor.py
      test_managed_markdown.py
```

Responsibilities:

- `models.py`: immutable plan, action, fingerprint and manifest data contracts plus deterministic JSON serialization.
- `templates.py`: canonical paths, version constants, template/legacy asset lookup, hashing and manifest construction.
- `managed_markdown.py`: parse, validate and replace stable Norn managed blocks without touching project-owned text.
- `analyzer.py`: classify repository state, determine ownership evidence and produce plan artifacts without writes.
- `executor.py`: revalidate preconditions, stage output, apply confirmed actions, remove safe empty directories and verify invariants.
- `manage_norn_governance.py`: thin CLI around analyze/apply/report operations.
- `SKILL.md`: concise natural-language routing, user confirmation and semantic conflict choices.
- `references/recovery-plans.md`: conditional instructions and safe template loaded only when a task must cross sessions or devices.

---

### Task 1: Hard-Rename the Skill Without Behavioral Drift

**Files:**
- Move: `skills/init-ai-project/` -> `skills/norn-governance/`
- Move: `skills/norn-governance/scripts/init_ai_project.py` -> `skills/norn-governance/scripts/manage_norn_governance.py`
- Move: `skills/norn-governance/tests/test_init_ai_project.py` -> `skills/norn-governance/tests/test_cli.py`
- Modify: `skills/norn-governance/SKILL.md`
- Modify: `skills/norn-governance/agents/openai.yaml`
- Modify: `skills/norn-governance/tests/test_cli.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: current five-file initializer behavior and current Norn template assets.
- Produces: `$norn-governance`, `skills/norn-governance/`, `scripts/manage_norn_governance.py`; no old callable path remains.

- [ ] **Step 1: Move the source tree and executable entrypoint**

```bash
git mv skills/init-ai-project skills/norn-governance
git mv skills/norn-governance/scripts/init_ai_project.py \
  skills/norn-governance/scripts/manage_norn_governance.py
git mv skills/norn-governance/tests/test_init_ai_project.py \
  skills/norn-governance/tests/test_cli.py
```

- [ ] **Step 2: Update test entrypoint and run the renamed suite**

Change `SCRIPT` in `test_cli.py` to:

```python
SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "manage_norn_governance.py"
```

Run:

```bash
python3 -m unittest discover -s skills/norn-governance/tests -v
```

Expected: the existing three tests pass from the new path before lifecycle behavior changes.

- [ ] **Step 3: Hard-switch skill metadata and repository docs**

Set discriminating frontmatter and UI identifiers to:

```yaml
name: norn-governance
description: 初始化、迁移或升级项目中的 Norn AI 协作治理，安全处理旧 docs 治理路径和受管区块冲突。适用于用户要求建立、迁移或更新 Norn 治理；不适用于与 Norn 无关的普通项目文档编辑。
```

```yaml
interface:
  display_name: "Norn Governance"
  short_description: "初始化、迁移和升级项目中的 Norn AI 协作治理"
  default_prompt: "使用 $norn-governance 管理当前项目的 Norn AI 治理。"
```

Quote every `openai.yaml` string, preserve automatic skill discovery, and do not add `policy.allow_implicit_invocation: false` because the user did not request explicit-only invocation. Update README paths and examples to `skills/norn-governance/` and `$norn-governance`. Remove all live instructions that advertise `init-ai-project`; references in Git history or the implementation spec remain historical evidence, not callable interfaces.

- [ ] **Step 4: Validate hard-switch invariants**

Run:

```bash
test ! -e skills/init-ai-project
test ! -e skills/norn-governance/scripts/init_ai_project.py
rg -n 'init-ai-project|init_ai_project' README.md skills/norn-governance
python3 /Users/leazer/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  skills/norn-governance
```

Expected: both `test` commands pass; `rg` has no output; skill validation reports `Skill is valid!`.

- [ ] **Step 5: Commit the hard rename**

```bash
git add -A README.md skills
git commit -m "Rename skill to Norn Governance"
```

---

### Task 2: Define Deterministic Plan and Manifest Contracts

**Files:**
- Create: `skills/norn-governance/scripts/norn_governance/__init__.py`
- Create: `skills/norn-governance/scripts/norn_governance/models.py`
- Create: `skills/norn-governance/tests/test_analyzer.py`
- Modify: `skills/norn-governance/scripts/manage_norn_governance.py`

**Interfaces:**
- Produces: `ProjectState`, `ActionKind`, `PathKind`, `OwnershipKind`, `ConflictChoice`, `PathFingerprint`, `PlannedAction`, `GovernancePlan`, `NornManifest`, `load_plan(path)`, and `write_plan(plan, directory)`.
- Later tasks consume the exact field names and deterministic plan digest defined here.

- [ ] **Step 1: Write failing serialization and digest tests**

Add tests inside a `unittest.TestCase` so the selected runner actually executes them; construct plans independently of production helpers:

```python
import unittest

from norn_governance.models import (
    ActionKind,
    GovernancePlan,
    OwnershipKind,
    PathFingerprint,
    PlannedAction,
    ProjectState,
)


class PlanModelTests(unittest.TestCase):
    def test_plan_digest_is_stable_and_excludes_its_own_digest(self) -> None:
        action = PlannedAction(
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
        plan = GovernancePlan.build(
            target_root="/tmp/example",
            project_state=ProjectState.UNINITIALIZED,
            template_version=1,
            actions=(action,),
            conflicts=(),
        )

        self.assertEqual(len(plan.plan_sha256), 64)
        self.assertEqual(plan.to_dict()["plan_sha256"], plan.plan_sha256)
        self.assertEqual(
            GovernancePlan.from_dict(plan.to_dict()).to_dict(), plan.to_dict()
        )
```

Also test `PathFingerprint.missing()`, a file fingerprint, directory fingerprint, enum JSON values, deep collection immutability, and rejection of a tampered `plan_sha256`. Add manifest round-trip and validation tests for unsupported schema versions, negative template versions, unknown ownership, invalid SHA-256 and missing managed-block metadata; a nonnegative older template version remains valid input for upgrade analysis.

- [ ] **Step 2: Run tests and verify RED**

```bash
python3 -m unittest skills/norn-governance/tests/test_analyzer.py -v
```

Expected: import failure because `norn_governance.models` does not exist.

- [ ] **Step 3: Implement immutable models and canonical JSON**

Define these contracts in `models.py`:

```python
class ProjectState(str, Enum):
    UNINITIALIZED = "uninitialized"
    CURRENT = "current"
    UPGRADEABLE = "upgradeable"
    LEGACY = "legacy"
    MIXED = "mixed"
    AMBIGUOUS = "ambiguous"
    CONFLICT = "conflict"


class ActionKind(str, Enum):
    CREATE = "create"
    MOVE = "move"
    MERGE = "merge"
    DELETE = "delete"
    KEEP = "keep"
    CONFLICT = "conflict"


class PathKind(str, Enum):
    MISSING = "missing"
    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    OTHER = "other"


class OwnershipKind(str, Enum):
    MANAGED = "managed"
    MIXED = "mixed"
    PROJECT = "project"


class ConflictChoice(str, Enum):
    KEEP_CURRENT = "keep-current"
    ADOPT_TEMPLATE = "adopt-template"
    SEMANTIC_MERGE = "semantic-merge"


@dataclass(frozen=True)
class PathFingerprint:
    exists: bool
    kind: PathKind
    sha256: str | None


@dataclass(frozen=True)
class PlannedAction:
    action_id: str
    kind: ActionKind
    source_path: str | None
    target_path: str
    source_before: PathFingerprint | None
    target_before: PathFingerprint
    output_sha256: str | None
    ownership: OwnershipKind
    evidence: tuple[str, ...]
    reason: str
    risk: str
    verification: tuple[str, ...]
    allowed_resolutions: tuple[ConflictChoice, ...]


@dataclass(frozen=True)
class GovernancePlan:
    plan_schema_version: int
    target_root: str
    project_state: ProjectState
    template_version: int
    actions: tuple[PlannedAction, ...]
    conflicts: tuple[str, ...]
    plan_sha256: str
```

`ActionKind` has one exact meaning everywhere: `create` writes a missing target; `move` writes byte-identical source content to a new target and then removes the source; `merge` writes a rendered target and removes its legacy source only after verification; `delete` removes the path named by `target_path` and has no output artifact; `keep` performs no mutation; `conflict` makes the plan non-executable. `allowed_resolutions` is empty except on `conflict` actions. Equal-content destination collisions therefore produce `keep` for the canonical target plus a separate `delete` action for the verified duplicate legacy source, never an implicit deletion hidden inside `keep`.

`fingerprint_path()` hashes regular-file bytes. For a directory it hashes canonical JSON containing each immediate child name and kind in sorted order, so additions between analysis and apply invalidate planned directory cleanup. Symlinks and every unsupported filesystem object classify as `conflict`; the executor never follows them. Canonical plan JSON uses UTF-8, `ensure_ascii=False`, `sort_keys=True`, and compact separators for hashing. `GovernancePlan.from_dict()` recalculates the digest and raises `ValueError("plan digest mismatch")` when it differs.

Define manifest contracts:

```python
@dataclass(frozen=True)
class ManagedFileRecord:
    ownership: OwnershipKind
    base_sha256: str | None
    managed_blocks: tuple[str, ...]
    template_version: int


@dataclass(frozen=True)
class NornManifest:
    schema_version: int
    template_version: int
    managed_files: Mapping[str, ManagedFileRecord]
```

Normalize `managed_files` to a sorted `MappingProxyType` in construction and all sequence fields to tuples in `__post_init__`; callers may pass ordinary mappings and iterables, but published model instances are deeply immutable at their collection boundaries.

- [ ] **Step 4: Add plan artifact IO**

Implement:

```python
def write_plan(plan: GovernancePlan, directory: Path) -> Path:
    """Write plan.json atomically and return its path."""


def load_plan(path: Path) -> GovernancePlan:
    """Read, validate and return a plan; reject invalid digest or schema."""
```

Generated file bodies belong in `directory / "rendered" / f"{action_id}.content"`; the plan stores only their SHA-256 and resolves artifacts only through that convention. Machine plans and rendered bodies stay together in the system artifact directory. They are distinct from short repository recovery plans, which contain no file body, absolute temporary path or executable approval and always require fresh analysis before resuming on another device.

- [ ] **Step 5: Run tests and commit**

```bash
python3 -m unittest skills/norn-governance/tests/test_analyzer.py -v
git add skills/norn-governance/scripts skills/norn-governance/tests/test_analyzer.py
git commit -m "Add Norn migration plan contracts"
```

Expected: all plan model tests pass.

---

### Task 3: Add Versioned Managed Templates and Block Operations

**Files:**
- Create: `template/norn-governance/.norn.json`
- Create: `skills/norn-governance/scripts/norn_governance/managed_markdown.py`
- Create: `skills/norn-governance/scripts/norn_governance/templates.py`
- Create: `skills/norn-governance/tests/test_managed_markdown.py`
- Modify: `template/AGENTS.md`
- Modify: `template/norn-governance/AGENTS.md`
- Modify: `template/norn-governance/spec/AGENTS.md`
- Modify: `template/norn-governance/appendix/README.md`
- Modify: `skills/norn-governance/assets/ai-project-governance-template/**`
- Modify: `skills/norn-governance/tests/test_cli.py`

**Interfaces:**
- Produces: `TEMPLATE_VERSION = 1`, `MANIFEST_SCHEMA_VERSION = 1`, `parse_managed_blocks(text)`, `replace_managed_block(text, block_id, replacement)`, `template_manifest(template_root)` and six-file initialization output.
- `main-spec.md` remains project-owned and contains no managed block.

- [ ] **Step 1: Write failing managed-block tests**

```python
import unittest

from norn_governance.managed_markdown import (
    ManagedBlockError,
    parse_managed_blocks,
    replace_managed_block,
)


class ManagedMarkdownTests(unittest.TestCase):
    def test_replace_managed_block_preserves_project_text(self) -> None:
        current = (
            "before\n"
            "<!-- norn:managed:start core-governance -->\nold\n"
            "<!-- norn:managed:end core-governance -->\n"
            "after\n"
        )
        replacement = (
            "<!-- norn:managed:start core-governance -->\nnew\n"
            "<!-- norn:managed:end core-governance -->"
        )

        self.assertEqual(
            replace_managed_block(current, "core-governance", replacement),
            "before\n" + replacement + "\nafter\n",
        )

    def test_duplicate_managed_block_is_rejected(self) -> None:
        duplicated = (
            "<!-- norn:managed:start core-governance -->x"
            "<!-- norn:managed:end core-governance -->\n"
            "<!-- norn:managed:start core-governance -->y"
            "<!-- norn:managed:end core-governance -->"
        )
        with self.assertRaises(ManagedBlockError):
            parse_managed_blocks(duplicated)
```

Also cover a missing end marker, nested blocks, an unknown block ID and UTF-8 content outside blocks.

- [ ] **Step 2: Run tests and verify RED**

```bash
python3 -m unittest skills/norn-governance/tests/test_managed_markdown.py -v
```

Expected: import failure because `managed_markdown.py` does not exist.

- [ ] **Step 3: Implement managed block parsing and replacement**

Use exact markers:

```python
START_PREFIX = "<!-- norn:managed:start "
END_PREFIX = "<!-- norn:managed:end "


@dataclass(frozen=True)
class ManagedBlock:
    block_id: str
    start: int
    end: int
    text: str
    sha256: str
```

Reject malformed, duplicate or nested managed blocks. Replacement must preserve every byte outside the selected block except the single newline needed to keep valid Markdown separation.

Use these public signatures:

```python
def parse_managed_blocks(text: str) -> Mapping[str, ManagedBlock]: ...
def replace_managed_block(text: str, block_id: str, replacement: str) -> str: ...
def template_manifest(template_root: Path) -> NornManifest: ...
```

- [ ] **Step 4: Mark canonical governance content**

Wrap Norn-owned content in the four governed Markdown files with stable IDs:

```text
AGENTS.md                                      core-governance
norn-governance/AGENTS.md                     governance-directory
norn-governance/spec/AGENTS.md                specification-governance
norn-governance/appendix/README.md            appendix-governance
```

Do not add markers to `norn-governance/spec/main-spec.md`.

- [ ] **Step 5: Generate and validate `.norn.json`**

In `templates.py` define:

```python
TEMPLATE_VERSION = 1
MANIFEST_SCHEMA_VERSION = 1
MANAGED_PATHS = {
    "AGENTS.md": (OwnershipKind.MIXED, ("core-governance",)),
    "norn-governance/AGENTS.md": (OwnershipKind.MIXED, ("governance-directory",)),
    "norn-governance/spec/AGENTS.md": (OwnershipKind.MIXED, ("specification-governance",)),
    "norn-governance/spec/main-spec.md": (OwnershipKind.PROJECT, ()),
    "norn-governance/appendix/README.md": (OwnershipKind.MIXED, ("appendix-governance",)),
}
```

`template_manifest()` computes actual template block hashes and emits schema/template version `1`. Write the resulting deterministic JSON to `template/norn-governance/.norn.json`, then synchronize all six files to the skill asset.

- [ ] **Step 6: Update initialization behavior test-first**

Change `EXPECTED_FILES` to include `norn-governance/.norn.json`. Add runtime assertions:

```python
manifest = json.loads((target / "norn-governance/.norn.json").read_text())
self.assertEqual(manifest["schema_version"], 1)
self.assertEqual(manifest["template_version"], 1)
self.assertEqual(manifest["managed_files"]["norn-governance/spec/main-spec.md"]["ownership"], "project")
self.assertNotIn("norn:managed", (target / "norn-governance/spec/main-spec.md").read_text())
```

Run the test before changing initialization and observe the missing manifest failure; then update the script to create the computed manifest as the sixth file.

- [ ] **Step 7: Verify templates and commit**

```bash
python3 -m unittest discover -s skills/norn-governance/tests -v
python3 /Users/leazer/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  skills/norn-governance
for relative_file in \
  AGENTS.md \
  norn-governance/.norn.json \
  norn-governance/AGENTS.md \
  norn-governance/spec/AGENTS.md \
  norn-governance/spec/main-spec.md \
  norn-governance/appendix/README.md; do
  cmp "template/$relative_file" \
    "skills/norn-governance/assets/ai-project-governance-template/$relative_file"
done
git add template skills/norn-governance
git commit -m "Add versioned Norn managed templates"
```

---

### Task 4: Classify Legacy Ownership and Build Migration Plans

**Files:**
- Create: `skills/norn-governance/assets/legacy-templates/0/**`
- Create: `skills/norn-governance/scripts/norn_governance/analyzer.py`
- Modify: `skills/norn-governance/scripts/norn_governance/templates.py`
- Modify: `skills/norn-governance/tests/test_analyzer.py`

**Interfaces:**
- Produces: `fingerprint_path(path)`, `classify_project(target_root)`, `analyze_governance(target_root, artifact_root)`, exact-template migration artifacts and unresolved semantic-conflict actions.
- Consumes: plan contracts, canonical templates, managed block parser and legacy version `0` snapshot.

- [ ] **Step 1: Add the exact legacy version-0 snapshot**

Recover the last pre-Norn template from Git history into the skill package:

```bash
git ls-tree -r --name-only 0c01ea23f0b1e699ccb05ed74608d0cf935d9409 template
mkdir -p skills/norn-governance/assets/legacy-templates/0
git archive 0c01ea23f0b1e699ccb05ed74608d0cf935d9409:template \
  | tar -x -C skills/norn-governance/assets/legacy-templates/0
```

The tree listing must be exactly `template/AGENTS.md` plus the four mapped `template/docs/` governance files before extraction; abort if the historical tree differs. After extraction, assert `find skills/norn-governance/assets/legacy-templates/0 -type f | wc -l` is `5` and no Finder metadata or unrelated file exists.

- [ ] **Step 2: Write failing state-classification tests**

Use temporary directories and literal expected states:

```python
def test_isolated_legacy_named_spec_is_ambiguous(self) -> None:
    target = self.make_target()
    self.write(target, "docs/spec/main-spec.md", "# Existing product spec\n")

    plan = analyze_governance(target, self.artifacts())

    self.assertEqual(plan.project_state, ProjectState.AMBIGUOUS)
    self.assertEqual(plan.actions[0].kind, ActionKind.CONFLICT)


def test_complete_legacy_bundle_is_classified_as_legacy(self) -> None:
    target = self.copy_legacy_template()

    plan = analyze_governance(target, self.artifacts())

    self.assertEqual(plan.project_state, ProjectState.LEGACY)
    self.assertEqual(
        {(a.source_path, a.target_path, a.kind) for a in plan.actions if a.source_path},
        {
            ("docs/AGENTS.md", "norn-governance/AGENTS.md", ActionKind.MERGE),
            ("docs/spec/AGENTS.md", "norn-governance/spec/AGENTS.md", ActionKind.MERGE),
            ("docs/spec/main-spec.md", "norn-governance/spec/main-spec.md", ActionKind.MERGE),
            ("docs/appendix/README.md", "norn-governance/appendix/README.md", ActionKind.MERGE),
        },
    )
```

The exact snapshot uses `merge`, not `move`, because every destination is rendered with either current managed markers or an exact governance-path rewrite; `move` is reserved for byte-identical relocation. Also cover uninitialized, current, upgradeable, mixed, directory-at-file-path, malformed or future-version manifest becoming `conflict`, exact legacy hash recognition, structurally recognized customized governance files becoming conflicts, equal destination content becoming explicit duplicate deletion, and non-governance `docs/` files remaining absent from all mutating actions.

- [ ] **Step 3: Run tests and verify RED**

```bash
python3 -m unittest \
  skills/norn-governance/tests/test_analyzer.py -v
```

Expected: import failure for `analyzer.analyze_governance`.

- [ ] **Step 4: Implement deterministic ownership evidence**

Implement these rules:

```python
LEGACY_PATH_MAP = {
    "docs/AGENTS.md": "norn-governance/AGENTS.md",
    "docs/spec/AGENTS.md": "norn-governance/spec/AGENTS.md",
    "docs/spec/main-spec.md": "norn-governance/spec/main-spec.md",
    "docs/appendix/README.md": "norn-governance/appendix/README.md",
}
```

Use these public signatures:

```python
def fingerprint_path(path: Path) -> PathFingerprint: ...
def classify_project(target_root: Path) -> ProjectState: ...
def analyze_governance(target_root: Path, artifact_root: Path) -> GovernancePlan: ...
```

An individual existing file is confirmed legacy when its bytes equal the corresponding version-0 snapshot. A customized bundle is confirmed only when all three structural facts hold:

1. Root `AGENTS.md` references `docs/AGENTS.md` and `docs/spec/main-spec.md`.
2. `docs/AGENTS.md` defines both `spec/` and `appendix/` responsibilities.
3. `docs/spec/AGENTS.md` declares `main-spec.md` as the implementation authority.

An isolated matching path without exact legacy hash is `ambiguous`, never `legacy`. A partial set containing exact version-0 bytes has confirmed ownership for those files but classifies as `mixed`, because it may be an interrupted or partial migration rather than a complete old installation.

- [ ] **Step 5: Build migration plan artifacts**

For confirmed legacy bundles:

- when a governance file exactly matches the known version-0 template, deterministically render the current marked template; when it is structurally owned but customized, create a `conflict` action with `allowed_resolutions=(ConflictChoice.ADOPT_TEMPLATE, ConflictChoice.SEMANTIC_MERGE)` and do not invent merged text;
- preserve the full project-owned `main-spec.md` body and replace only the exact known references `docs/AGENTS.md`, `docs/spec/AGENTS.md`, `docs/spec/main-spec.md` and `docs/appendix/README.md`; unrelated occurrences of the word `docs` remain unchanged;
- plan root `AGENTS.md` as an in-place `merge` when it exactly matches the old baseline; if it contains custom text and no reliable managed boundary, require `semantic-merge` or `adopt-template` rather than heuristically splitting sections;
- add `.norn.json` creation only to a fully resolved plan, because writing the success marker while semantic conflicts remain would falsely mark migration complete;
- write every rendered body under `artifact_root/rendered/` and bind its hash to its action;
- when a destination is byte-identical to the planned output, emit `keep` for the canonical target and a separate, fingerprinted `delete` for the duplicate legacy source; when it differs, emit `conflict` and do not plan source deletion;
- emit fingerprinted `delete` actions for `docs/spec`, `docs/appendix` and `docs` only when they will be empty after planned legacy-file removal; `docs` containing `architecture.md` or any other project file is kept.

- [ ] **Step 6: Run analyzer tests and commit**

```bash
python3 -m unittest skills/norn-governance/tests/test_analyzer.py -v
git add skills/norn-governance/assets/legacy-templates \
  skills/norn-governance/scripts/norn_governance \
  skills/norn-governance/tests/test_analyzer.py
git commit -m "Plan safe legacy Norn migrations"
```

---

### Task 5: Resolve Semantic Conflicts and Plan Versioned Upgrades

**Files:**
- Modify: `skills/norn-governance/scripts/norn_governance/analyzer.py`
- Modify: `skills/norn-governance/scripts/norn_governance/managed_markdown.py`
- Modify: `skills/norn-governance/scripts/norn_governance/models.py`
- Modify: `skills/norn-governance/tests/test_analyzer.py`
- Modify: `skills/norn-governance/tests/test_managed_markdown.py`

**Interfaces:**
- Produces: `ConflictChoice`, `resolve_conflicts(plan, choices, artifact_root)` and deterministic upgrade plans.
- Consumes: legacy semantic-conflict actions, `.norn.json` base hashes and current template blocks.

- [ ] **Step 1: Write failing upgrade tests**

```python
def test_unmodified_managed_block_is_upgraded_and_project_text_is_preserved(self) -> None:
    target = self.copy_versioned_project(template_version=0)
    self.append(target, "AGENTS.md", "\n## Project Rule\nKeep this.\n")

    plan = analyze_governance(target, self.artifacts())

    self.assertEqual(plan.project_state, ProjectState.UPGRADEABLE)
    root_action = self.action_for(plan, "AGENTS.md")
    self.assertEqual(root_action.kind, ActionKind.MERGE)
    rendered = self.rendered_text(root_action)
    self.assertIn("## Project Rule\nKeep this.", rendered)
    self.assertIn("## 整体性与变更边界", rendered)


def test_modified_managed_block_requires_explicit_choice(self) -> None:
    target = self.copy_versioned_project(template_version=0)
    self.modify_managed_block(target, "AGENTS.md", "project customized managed text")

    plan = analyze_governance(target, self.artifacts())

    root_action = self.action_for(plan, "AGENTS.md")
    self.assertEqual(root_action.kind, ActionKind.CONFLICT)
    self.assertIn("managed block differs from recorded base", root_action.reason)


def test_customized_legacy_governance_requires_semantic_output(self) -> None:
    target = self.copy_legacy_template()
    self.append(target, "docs/AGENTS.md", "\n## Project Docs Rule\nKeep this.\n")

    plan = analyze_governance(target, self.artifacts())

    action = self.action_for(plan, "norn-governance/AGENTS.md")
    self.assertEqual(action.kind, ActionKind.CONFLICT)
    self.assertEqual(
        action.allowed_resolutions,
        (ConflictChoice.ADOPT_TEMPLATE, ConflictChoice.SEMANTIC_MERGE),
    )
```

`copy_versioned_project(template_version=0)` is a test-only synthetic prior version: copy the current six-file template, replace the root `core-governance` block with a literal older marked block, set the manifest and every record to template version `0`, and set the root record's `base_sha256` to the SHA-256 of that exact older block. This exercises the real baseline-hash algorithm without claiming version `0` was a released manifest format. Also test `keep-current`, `adopt-template`, and `semantic-merge` choices; semantic merge must reference a rendered artifact whose hash is included in the resolved plan.

- [ ] **Step 2: Run tests and verify RED**

```bash
python3 -m unittest \
  skills/norn-governance/tests/test_analyzer.py \
  skills/norn-governance/tests/test_managed_markdown.py -v
```

Expected: upgrade or conflict-choice assertions fail because only legacy planning exists.

- [ ] **Step 3: Define explicit conflict choices**

```python
@dataclass(frozen=True)
class ConflictResolution:
    action_id: str
    choice: ConflictChoice
    rendered_path: str | None = None
    rendered_sha256: str | None = None
```

`SEMANTIC_MERGE` requires a UTF-8 artifact file and matching SHA-256. The engine never invents semantic merge content; the skill orchestration layer supplies it after explaining the proposed fusion to the user.

Implement the exact resolver contract:

```python
def resolve_conflicts(
    plan: GovernancePlan,
    choices: tuple[ConflictResolution, ...],
    artifact_root: Path,
) -> GovernancePlan:
    """Validate every conflict choice, canonicalize artifacts and rebuild digest."""
```

Reject missing or duplicate choices, choices not listed by `action.allowed_resolutions`, extra choices for non-conflict actions, artifact paths outside `artifact_root`, invalid UTF-8 and hash mismatches. `semantic-merge` copies the validated body atomically to `rendered/<action_id>.content`; `adopt-template` renders the canonical template through the analyzer; `keep-current` is allowed only for an already-versioned modified block and turns that file action into `keep`. Rebuild each resolved action, the final manifest artifact and the whole plan digest—never mutate the original frozen plan.

- [ ] **Step 4: Implement upgrade analysis**

For every managed block:

- compare current block hash with the manifest base hash;
- auto-render the current template block when they match;
- preserve bytes outside the block;
- create `conflict` with all three `ConflictChoice` values in `allowed_resolutions` when they differ;
- never plan template replacement for `main-spec.md`;
- render an updated `.norn.json` only after every conflict is resolved; its base hashes match the chosen final blocks and its template version advances atomically with the completed upgrade.

- [ ] **Step 5: Run all analyzer/block tests and commit**

```bash
python3 -m unittest \
  skills/norn-governance/tests/test_analyzer.py \
  skills/norn-governance/tests/test_managed_markdown.py -v
git add skills/norn-governance/scripts/norn_governance \
  skills/norn-governance/tests
git commit -m "Plan versioned Norn governance upgrades"
```

---

### Task 6: Execute Confirmed Plans Without Losing Source Content

**Files:**
- Create: `skills/norn-governance/scripts/norn_governance/executor.py`
- Create: `skills/norn-governance/tests/test_executor.py`
- Modify: `skills/norn-governance/scripts/norn_governance/models.py`

**Interfaces:**
- Produces: `apply_plan(plan_path) -> ApplyResult`, `verify_governance(target_root) -> VerificationResult`, `PlanPreconditionError`, `PlanArtifactError` and `PlanConflictError`.
- Consumes: fully resolved plan with no `conflict` actions and rendered artifacts bound by SHA-256.

- [ ] **Step 1: Write failing precondition and source-preservation tests**

```python
def test_apply_rejects_target_changed_after_analysis(self) -> None:
    target, plan_path = self.legacy_plan()
    self.write(target, "docs/spec/main-spec.md", "changed after confirmation\n")

    with self.assertRaisesRegex(PlanPreconditionError, "fingerprint changed"):
        apply_plan(plan_path)

    self.assertTrue((target / "docs/spec/main-spec.md").is_file())
    self.assertFalse((target / "norn-governance/spec/main-spec.md").exists())


def test_failed_destination_validation_does_not_delete_legacy_source(self) -> None:
    target, plan_path = self.legacy_plan(corrupt_rendered="root-agents")

    with self.assertRaisesRegex(PlanArtifactError, "rendered artifact hash mismatch"):
        apply_plan(plan_path)

    self.assertTrue((target / "docs/AGENTS.md").is_file())
    self.assertTrue((target / "docs/spec/main-spec.md").is_file())
```

Also cover a plan with unresolved conflicts, directory-at-file-path, unsupported schema, and a plan whose target root differs from the plan artifact.

Add an injected write-failure test after one non-manifest target has been replaced; it may leave verified new targets for `mixed` recovery, but every legacy source must still exist because source deletion has not begun.

- [ ] **Step 2: Run tests and verify RED**

```bash
python3 -m unittest skills/norn-governance/tests/test_executor.py -v
```

Expected: import failure because `executor.py` does not exist.

- [ ] **Step 3: Implement full preflight before writes**

Define:

```python
@dataclass(frozen=True)
class ApplyResult:
    created: tuple[str, ...]
    updated: tuple[str, ...]
    removed: tuple[str, ...]
    removed_directories: tuple[str, ...]
    verification: "VerificationResult"


@dataclass(frozen=True)
class VerificationResult:
    state: ProjectState
    manifest_valid: bool
    single_spec_source: bool
    checked_paths: tuple[str, ...]
    warnings: tuple[str, ...]


def apply_plan(plan_path: Path) -> ApplyResult:
    plan = load_plan(plan_path)
    validate_no_conflicts(plan)
    validate_all_preconditions(plan)
    validate_all_rendered_artifacts(plan_path.parent, plan)
    staged = stage_all_outputs(plan_path.parent, plan)
    return apply_staged_outputs(plan, staged)
```

Define the three error classes as `RuntimeError` subclasses and use them consistently for changed fingerprints, invalid/missing artifacts and unresolved conflicts. No target writes occur until every source, target and planned directory fingerprint plus every rendered artifact has passed preflight. Reject absolute action paths, `..` traversal, symlinks and any resolved path outside `plan.target_root` before staging.

- [ ] **Step 4: Implement safe write/move/delete ordering**

For each non-manifest target, write a sibling temporary file, copy mode bits where applicable, `fsync`, then call `os.replace`. Verify every non-manifest target SHA-256 before deleting any source; a later target failure must not strand an earlier source. Then process explicit duplicate-file and legacy-source deletion actions whose canonical targets are verified, followed by planned directory deletions in child-first order using only `Path.rmdir()`. Unexpected non-empty directories are preserved and reported, never recursively removed.

Write `.norn.json` last. If a process stops before that marker, the next analyzer run must classify the result as `mixed` and produce completion/recovery actions.

- [ ] **Step 5: Test successful migration and idempotency**

```python
def test_complete_migration_preserves_other_docs_and_is_idempotent(self) -> None:
    target, plan_path = self.legacy_plan()
    self.write(target, "docs/architecture.md", "project-owned\n")
    original_spec = (target / "docs/spec/main-spec.md").read_text()

    result = apply_plan(plan_path)

    self.assertEqual(
        (target / "norn-governance/spec/main-spec.md").read_text(),
        original_spec.replace(
            "docs/spec/AGENTS.md", "norn-governance/spec/AGENTS.md"
        ),
    )
    self.assertEqual((target / "docs/architecture.md").read_text(), "project-owned\n")
    self.assertFalse((target / "docs/spec").exists())
    second_plan = analyze_governance(target, self.artifacts())
    self.assertEqual(second_plan.project_state, ProjectState.CURRENT)
    self.assertFalse([a for a in second_plan.actions if a.kind not in {ActionKind.KEEP}])
```

- [ ] **Step 6: Run executor suite and commit**

```bash
python3 -m unittest skills/norn-governance/tests/test_executor.py -v
git add skills/norn-governance/scripts/norn_governance \
  skills/norn-governance/tests/test_executor.py
git commit -m "Execute Norn migrations safely"
```

---

### Task 7: Wire Skill-Orchestrated Analyze, Confirm and Apply UX

**Files:**
- Modify: `skills/norn-governance/scripts/manage_norn_governance.py`
- Modify: `skills/norn-governance/SKILL.md`
- Create: `skills/norn-governance/references/recovery-plans.md`
- Modify: `skills/norn-governance/tests/test_cli.py`
- Modify: `skills/norn-governance/agents/openai.yaml`
- Modify: `README.md`

**Interfaces:**
- Produces internal CLI commands `analyze` and `apply`, JSON/human reports, and the complete `$norn-governance` user workflow.
- Consumes: analyzer plans, conflict resolutions and executor results.

- [ ] **Step 1: Write failing end-to-end CLI tests**

```python
def test_analyze_legacy_project_writes_plan_but_not_project_files(self) -> None:
    target = self.copy_legacy_template()
    before = self.snapshot(target)

    report = self.run_cli("analyze", "--target", target, "--report-json")

    self.assertEqual(report["project_state"], "legacy")
    self.assertTrue(Path(report["plan_path"]).is_file())
    self.assertEqual(self.snapshot(target), before)
    self.assertIn(
        "docs/AGENTS.md", {action["source_path"] for action in report["actions"]}
    )


def test_apply_requires_plan_artifact(self) -> None:
    target = self.make_target()
    completed = self.run_cli_raw("apply", "--target", target)
    self.assertNotEqual(completed.returncode, 0)
    self.assertIn("--plan", completed.stderr)
```

Also test a tampered plan digest is rejected and human report sections exist for state, ownership evidence, relocations, rule upgrades, conflicts, deletions, risks and verification. Assert structure and fields, not exact prose sentences.

- [ ] **Step 2: Run tests and verify RED**

```bash
python3 -m unittest skills/norn-governance/tests/test_cli.py -v
```

Expected: argument parsing fails because the CLI has no `analyze`/`apply` commands.

- [ ] **Step 3: Implement thin CLI subcommands**

```text
manage_norn_governance.py analyze --target <path> [--artifact-dir <path>] [--report-json]
manage_norn_governance.py apply --target <path> --plan <plan.json> [--report-json]
```

`analyze` defaults artifacts to a new system temporary directory and never mutates the target. `apply` requires a resolved, digest-valid plan whose target root equals `--target`.

- [ ] **Step 4: Rewrite SKILL.md around user intent**

The workflow must explicitly instruct the agent to:

1. Infer initialize/update/migrate intent and run `analyze` internally.
2. Inspect raw files when ownership is structural or ambiguous; do not trust path names alone.
3. Summarize all actions and choices in natural language without asking the user to run commands.
4. Ask once for all resolved operations; ask separate targeted questions only for ambiguous ownership or modified managed blocks.
5. Materialize semantic merge artifacts, resolve the plan, then run `apply` internally.
6. Verify content, paths, manifest, Git diff and single-spec-source invariant.
7. Leave commits and pushes to explicit user requests.

Keep ordinary analyze/migrate/upgrade routing in `SKILL.md`. Link `references/recovery-plans.md` at the point where cross-session persistence becomes relevant and instruct the agent to read it only for that mode; do not load recovery details for routine one-session initialization.

- [ ] **Step 5: Define short-lived cross-session recovery plans**

Put the detailed lifecycle in `references/recovery-plans.md`; `SKILL.md` keeps only the routing link and the invariant that ordinary machine plans remain in the system temporary directory. Only when the user explicitly needs to pause, cross sessions or cross devices may the skill create `norn-governance/plans/YYYY-MM-DD-<slug>.md`, creating `plans/` at that moment rather than during initialization. Use this exact safe shape:

```markdown
# <Task> Recovery Plan

- Intent: <initialize, migrate, or upgrade>
- Observed state: <state from last analysis>
- Governed paths: <relative paths only>
- Confirmed decisions: <semantic choices already made>
- Remaining conflicts: <items requiring user choice>
- Risks: <source deletion, collisions, or ownership ambiguity>
- Resume rule: rerun analysis, compare the new action summary, and obtain fresh confirmation before apply
```

Never include file bodies, secrets, absolute temporary paths, rendered-artifact paths or a reusable approval. On resume—even on the same device—rerun `analyze`; if fingerprints or actions changed, discard the old machine plan and explain the new diff. Delete the repository recovery plan when the task completes or the user cancels it. The skill may edit this file as part of governance work but may commit it only when the user explicitly asks for a commit.

- [ ] **Step 6: Update brand and help text completely**

Human reports and `--help` use `Norn Governance`, not the old generic “AI 项目治理初始化报告”. README explains initialization, migration, upgrade, managed blocks and `.norn.json` without exposing internal commands as the primary UX.

- [ ] **Step 7: Run CLI/full tests and commit**

```bash
python3 -m unittest discover -s skills/norn-governance/tests -v
python3 /Users/leazer/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  skills/norn-governance
git add README.md skills/norn-governance
git commit -m "Add Norn governance lifecycle workflow"
```

---

### Task 8: Full Migration Verification, Installation Sync and Plan Cleanup

**Files:**
- Delete after completion: `norn-governance/plans/2026-08-25-norn-governance-lifecycle.md`
- Replace local installation: `~/.codex/skills/init-ai-project/` -> `~/.codex/skills/norn-governance/`

**Interfaces:**
- Consumes: completed repository skill and all tests.
- Produces: verified source tree, current local installed skill, no old callable skill, and no completed temporary plan.

- [ ] **Step 1: Run the complete automated suite**

```bash
python3 -m unittest discover -s skills/norn-governance/tests -v
python3 /Users/leazer/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  skills/norn-governance
git diff --check
```

Expected: all tests pass, skill validation prints `Skill is valid!`, and `git diff --check` exits 0.

- [ ] **Step 2: Verify source template and skill assets byte-for-byte**

```bash
for relative_file in \
  AGENTS.md \
  norn-governance/.norn.json \
  norn-governance/AGENTS.md \
  norn-governance/spec/AGENTS.md \
  norn-governance/spec/main-spec.md \
  norn-governance/appendix/README.md; do
  cmp "template/$relative_file" \
    "skills/norn-governance/assets/ai-project-governance-template/$relative_file"
done
```

Expected: no output, exit 0.

- [ ] **Step 3: Run real temporary-project acceptance scenarios**

Use separate `mktemp -d` targets for:

1. Empty project: analyze -> apply -> analyze returns `current`.
2. Exact legacy snapshot: analyze returns `legacy`; apply relocates and upgrades only the four governed files.
3. Customized legacy main spec plus `docs/architecture.md`: business content and architecture doc remain.
4. Customized legacy governance entry: analyze does not synthesize merged text; apply remains unavailable until `semantic-merge` or `adopt-template` is explicitly resolved.
5. Isolated `docs/spec/main-spec.md`: analyze returns `ambiguous`; apply is unavailable until ownership is resolved.
6. Synthetic prior-version project with untouched blocks: analyze returns `upgradeable`; apply preserves project text.
7. Synthetic prior-version project with edited managed block: analyze includes `conflict` and requires explicit resolution.
8. Changed file after analysis: apply exits nonzero and writes nothing.
9. Injected mid-write failure: verified new targets may remain for `mixed` recovery, but every legacy source remains.
10. Equal-content destination: canonical file is kept and the separately planned duplicate source is deleted.
11. Repeated analyze/apply after success: no mutating actions.
12. Recovery-plan lifecycle: save only the safe Markdown fields, resume through fresh analysis, then delete the plan on completion and on cancellation.

For every scenario, inspect the JSON plan and the actual filesystem; do not infer acceptance from unit tests alone.

- [ ] **Step 4: Audit live references and final repository state**

```bash
rg -n 'init-ai-project|init_ai_project|skills/init-ai-project' \
  README.md template skills norn-governance/spec
git status --short
git diff --stat main...HEAD
```

Expected: no live old-name references outside explicit historical migration notes in the specification; only intended implementation changes are present.

- [ ] **Step 5: Synchronize the local installed skill after approval**

Stage a copy of the verified repository skill in a fresh `mktemp -d` directory. Move only the exact existing paths `/Users/leazer/.codex/skills/init-ai-project` and `/Users/leazer/.codex/skills/norn-governance`, when present, into that temporary backup; then move the staged `norn-governance` tree into `/Users/leazer/.codex/skills/norn-governance`. Compare the installed and source trees excluding Finder metadata and test bytecode before deleting the temporary backup. If copy or comparison fails, restore the previous paths from that backup and report failure rather than leaving two callable versions.

Required invariants:

```text
/Users/leazer/.codex/skills/init-ai-project does not exist
/Users/leazer/.codex/skills/norn-governance/SKILL.md exists
installed SKILL.md, agents/, references/, scripts/ and assets/ equal repository source
```

- [ ] **Step 6: Delete this completed temporary plan and commit final cleanup**

After every stable decision is present in `norn-governance/spec/main-spec.md`, README, skill instructions, templates and tests:

```bash
git add -A README.md template skills norn-governance
git diff --cached --check
git diff --cached --name-status
git commit -m "Finalize Norn governance migration"
```

Inspect the staged name-status list before committing and unstage anything outside the plan's declared paths. The commit must delete `norn-governance/plans/2026-08-25-norn-governance-lifecycle.md`; do not retain a completed plan archive or index.
