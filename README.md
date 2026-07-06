# AI 项目治理模板

一套可复制到项目仓库里的 AI 工程化治理模板，用来把 AI 协作中的长期依据收敛到少数稳定文件。

它把 AI 协作中的长期依据收敛到三大稳定来源：`docs/spec/` 负责主实现规格，代码负责真实实现，Git 历史负责追溯变更；根目录 `AGENTS.md` 负责约束 agent 如何使用这些来源。

主实现规格是项目骨骼，代码是项目皮肤和血肉。规格负责业务语义：目标、流程、边界、规则、失败处理和验收；代码负责实现事实：真实机制、当前可观察行为和可追溯代码路径。读代码、改代码和验收结果时都要主动识别规格是否落后；确定是稳定代码现实而规格落后时自动回写并用 `⚠️` 提示，不确定时用 `🚨` 询问，确认没有真实实现变动时用 `🔵` 说明无需回写。

主实现规格不是代码复述。它保存代码无法稳定表达、但决定业务语义等价性的内容；换一种语言、框架或代码结构后仍必须保持的信息才进入规格，只描述当前代码如何做到的信息留在代码里。

框架要求所有实现先回到第一性原理：真实用户、真实问题、可感知结果和验收方式。任何新增功能、组件、状态、依赖、文档或流程，都应能说明服务哪个真实需求；如果方向偏离最终目的，AI 应先提示风险并给出更小的可验证方案。

这些规则更偏方法论而不是知识清单：用少数稳定思想指导 AI 判断复杂度、边界、演化和取舍，同时避免把项目变成表格、流程和概念堆叠。

## 目录

```text
README.md
template/
  AGENTS.md
  docs/
    AGENTS.md
    spec/
      AGENTS.md
      main-spec.md
    appendix/
      README.md
skills/
  init-ai-project/
    SKILL.md
    scripts/
      init_ai_project.py
    assets/
      ai-project-governance-template/
```

## 推荐使用方式

优先使用 `skills/init-ai-project/` 里的 skill 初始化目标项目。它会先分析目标项目中缺失、相同或冲突的治理文件，默认不覆盖已有文件。

```bash
python3 skills/init-ai-project/scripts/init_ai_project.py --target <目标项目路径>
```

确认只需要写入缺失文件后再执行：

```bash
python3 skills/init-ai-project/scripts/init_ai_project.py --target <目标项目路径> --apply
```

若目标项目已有 `AGENTS.md` 或 `docs/` 规范文件，脚本会报告冲突和融合建议，不会自动覆盖。

## 手动使用方式

1. 将 `template/AGENTS.md` 和 `template/docs/` 复制到目标项目根目录。
2. 按项目情况修改 `docs/spec/main-spec.md`，必要时重命名为具体业务规格。
3. 后续让 AI 按项目内 `AGENTS.md` 工作。

具体执行流程、文档维护规则和规格边界都在模板文件中定义。

## 本机 skill 安装

仓库内 `skills/init-ai-project/` 是源码位置。需要让 Codex 本机自动发现时，将该目录同步到：

```text
~/.codex/skills/init-ai-project/
```

后续修改先更新仓库内源码，再同步到本机安装副本。
