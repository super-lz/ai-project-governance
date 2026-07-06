---
name: init-ai-project
description: 初始化 AI 项目治理文件，并分析目标仓库中缺失或冲突的 AGENTS.md/docs/spec 规范文件。Use when a user asks to initialize an AI project, copy the AI governance template, add AGENTS.md/docs/spec governance, or analyze an existing project for missing/conflicting AI collaboration files.
---

# 初始化 AI 项目

## 概览

使用本 skill 将 AI 项目治理模板初始化到目标仓库。首版只管理 `assets/ai-project-governance-template/` 中的治理文件；不创建应用代码、不修改 Git 配置、不提交代码，也不初始化 Flutter 专项工具链。

## 工作流程

1. 从用户请求或当前工作目录确认目标仓库根目录。
2. 先执行 dry-run 分析：

```bash
python3 <skill-dir>/scripts/init_ai_project.py --target <target-repo>
```

3. 查看报告：
   - `missing`：目标仓库缺少该文件，可以从模板创建。
   - `same`：目标仓库已有文件且内容与模板一致。
   - `conflict`：目标仓库已有同名文件，但内容与模板不同。
4. 如果存在冲突，先总结融合方案并询问用户，确认前不要编辑冲突文件。
5. 如果用户确认写入缺失文件，执行：

```bash
python3 <skill-dir>/scripts/init_ai_project.py --target <target-repo> --apply
```

## 冲突策略

- 永远不要自动覆盖目标仓库已有文件。
- 把冲突视为治理规则融合任务，而不是复制任务。
- 说明发生差异的具体路径；除非用户明确确认融合，否则保留目标项目已有规则。
- 对 `AGENTS.md`，优先融合模板里的稳定职责：项目总指挥入口、第一性原则、实现规格维护、文档治理。
- 对 `docs/` 下文件，如果目标项目已有更具体的文档分类，保留现有分类，只补缺失的治理规则。

## 脚本约定

`scripts/init_ai_project.py` 支持：

- `--target <path>`：目标仓库根目录，必填。
- `--apply`：只复制缺失文件。已有冲突文件永远不会被覆盖。
- `--report-json`：输出机器可读报告，便于后续自动化能力复用。

脚本使用固定文件清单：

- `AGENTS.md`
- `docs/AGENTS.md`
- `docs/spec/AGENTS.md`
- `docs/spec/main-spec.md`
- `docs/appendix/README.md`

## 本机安装

仓库内副本是源码基准。需要让本机 Codex 可用时，将 `skills/init-ai-project/` 同步到 `~/.codex/skills/init-ai-project/`。后续修改先更新仓库内源码，再同步本机安装副本。

## 后续扩展边界

Flutter 初始化应在 AI 治理初始化稳定后作为独立能力加入。不要在 v1 脚本中提前加入 Flutter 选项；Flutter 项目创建、lint/analyze 配置、pubspec 处理和 build_runner 集成都应作为单独工作流设计，并保留独立分析和用户选择。
