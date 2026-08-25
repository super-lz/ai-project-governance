---
name: norn-governance
description: 初始化、迁移或升级项目中的 Norn AI 协作治理，安全处理旧 docs 治理路径和受管区块冲突。适用于用户要求建立、迁移或更新 Norn 治理；不适用于与 Norn 无关的普通项目文档编辑。
---

# 初始化 Norn 项目治理

## 概览

使用本 skill 将 Norn AI 项目治理模板初始化到目标仓库。它保留根 `AGENTS.md` 作为标准入口，把规格、按需计划和附录统一放在 `norn-governance/` 命名空间中。首版只管理 `assets/ai-project-governance-template/` 中的固定治理文件；不创建应用代码、不修改 Git 配置、不提交代码，也不初始化 Flutter 专项工具链。

## 工作流程

1. 从用户请求或当前工作目录确认目标仓库根目录。
2. 先执行 dry-run 分析：

```bash
python3 <skill-dir>/scripts/manage_norn_governance.py --target <target-repo>
```

3. 查看报告：
   - `missing`：目标仓库缺少该文件，可以从模板创建。
   - `same`：目标仓库已有文件且内容与模板一致。
   - `conflict`：目标仓库已有同名文件，但内容与模板不同。
   - 包含 `legacy_path` 的 `conflict`：检测到旧版 `docs/` 治理路径，必须先确认迁移，不能直接创建第二套 Norn 规格。
4. 如果存在冲突，先总结融合方案并询问用户，确认前不要编辑冲突文件。
5. 如果用户确认写入缺失文件，执行：

```bash
python3 <skill-dir>/scripts/manage_norn_governance.py --target <target-repo> --apply
```

## 冲突策略

- 永远不要自动覆盖目标仓库已有文件。
- 把冲突视为治理规则融合任务，而不是复制任务。
- 说明发生差异的具体路径；除非用户明确确认融合，否则保留目标项目已有规则。
- 对 `AGENTS.md`，优先融合模板里的稳定职责：项目总指挥入口、第一性原则、实现规格维护、文档治理。
- 对 `norn-governance/` 下文件，保留目标项目已确认的规格和治理内容，只补缺失规则。
- 检测到旧版 `docs/AGENTS.md`、`docs/spec/` 或 `docs/appendix/README.md` 时，先分析这些文件是否确属旧 Norn 模板，再给出逐文件迁移方案；不要移动目标项目的其他 `docs/` 内容。
- 迁移确认前不要创建对应的新路径；迁移完成后不要长期保留两套权威规格。

## 脚本约定

`scripts/manage_norn_governance.py` 支持：

- `--target <path>`：目标仓库根目录，必填。
- `--apply`：只复制缺失文件。已有冲突文件永远不会被覆盖。
- `--report-json`：输出机器可读报告，便于后续自动化能力复用。

脚本使用固定文件清单：

- `AGENTS.md`
- `norn-governance/AGENTS.md`
- `norn-governance/spec/AGENTS.md`
- `norn-governance/spec/main-spec.md`
- `norn-governance/appendix/README.md`

`norn-governance/plans/` 不在固定文件清单中。只有任务预计跨会话、跨设备、步骤较多或容易中断时，才按根 `AGENTS.md` 和 Norn 治理入口的规则创建计划；完成或取消后删除计划。

## 本机安装

仓库内副本是源码基准。需要让本机 Codex 可用时，将 `skills/norn-governance/` 同步到 `~/.codex/skills/norn-governance/`。后续修改先更新仓库内源码，再同步本机安装副本。

## 后续扩展边界

Flutter 初始化应在 AI 治理初始化稳定后作为独立能力加入。不要在 v1 脚本中提前加入 Flutter 选项；Flutter 项目创建、lint/analyze 配置、pubspec 处理和 build_runner 集成都应作为单独工作流设计，并保留独立分析和用户选择。
