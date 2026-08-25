# Norn

面向 AI 协作开发的项目治理框架。Norn 把长期依据和短期执行状态放进职责明确、可选择加载的区域，减少跨会话、跨设备开发时的重复分析和记忆成本。

它把长期依据收敛到三大稳定来源：`norn-governance/spec/` 负责主实现规格，代码负责真实实现，Git 历史负责追溯变更；根目录 `AGENTS.md` 负责约束 agent 如何使用这些来源。`norn-governance/plans/` 只承接尚未完成任务的短期执行状态，不提升为第四种权威来源。

主实现规格是项目骨骼，代码是项目皮肤和血肉。规格负责业务语义：目标、流程、边界、规则、失败处理和验收；代码负责实现事实：真实机制、当前可观察行为和可追溯代码路径。读代码、改代码和验收结果时都要主动识别规格是否落后；确定是稳定代码现实而规格落后时自动回写并用 `⚠️` 提示，不确定时用 `🚨` 询问，确认没有真实实现变动时用 `🔵` 说明无需回写。

主实现规格不是代码复述。它保存代码无法稳定表达、但决定业务语义等价性的内容；换一种语言、框架或代码结构后仍必须保持的信息才进入规格，只描述当前代码如何做到的信息留在代码里。

框架要求所有实现先回到第一性原理：真实用户、真实问题、可感知结果和验收方式。任何新增功能、组件、状态、依赖、文档或流程，都应能说明服务哪个真实需求；如果方向偏离最终目的，AI 应先提示风险并给出更小的可验证方案。

这些规则更偏方法论而不是知识清单：用少数稳定思想指导 AI 判断复杂度、边界、演化和取舍，同时避免把项目变成表格、流程和概念堆叠。

## 目录

```text
README.md
template/
  AGENTS.md
  norn-governance/
    AGENTS.md
    spec/
      AGENTS.md
      main-spec.md
    plans/                 # 有未完成计划时按需创建
    appendix/
      README.md
skills/
  norn-governance/
    SKILL.md
    scripts/
      manage_norn_governance.py
    assets/
      ai-project-governance-template/
```

## 推荐使用方式

优先使用 `$norn-governance` skill 初始化目标项目。它会先分析目标项目中缺失、相同或冲突的 Norn 治理文件，默认不覆盖已有文件。仓库源码位于 `skills/norn-governance/`。

```bash
python3 skills/norn-governance/scripts/manage_norn_governance.py --target <目标项目路径>
```

确认只需要写入缺失文件后再执行：

```bash
python3 skills/norn-governance/scripts/manage_norn_governance.py --target <目标项目路径> --apply
```

若目标项目已有根 `AGENTS.md`、`norn-governance/` 文件或旧版 `docs/` 治理路径，脚本会报告冲突和融合建议，不会自动覆盖、自动移动或创建第二套规格。目标项目自己的其他 `docs/` 内容不属于 Norn 管理范围。

## 手动使用方式

1. 将 `template/AGENTS.md` 和 `template/norn-governance/` 复制到目标项目根目录。
2. 按项目情况修改 `norn-governance/spec/main-spec.md`，必要时重命名为具体业务规格。
3. 后续让 AI 按项目内 `AGENTS.md` 工作。

复杂或可能中断的任务可以在 `norn-governance/plans/` 创建计划并随分支提交；任务完成或取消后，将稳定结论回写规格、代码或测试，再删除计划。简单任务不创建计划文件。

具体执行流程、计划生命周期、文档维护规则和规格边界都在模板文件中定义。

## 本机 skill 安装

仓库内 `skills/norn-governance/` 是源码位置。需要让 Codex 本机自动发现时，将该目录同步到：

```text
~/.codex/skills/norn-governance/
```

后续修改先更新仓库内源码，再同步到本机安装副本。
