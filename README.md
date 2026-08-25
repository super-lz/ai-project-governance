# Norn

Norn 是面向 AI 协作开发的项目治理框架。它把长期依据和短期执行状态放进职责明确、可选择加载的区域，降低跨会话、跨设备开发时的重复分析和记忆成本。

长期事实收敛到三类来源：`norn-governance/spec/` 保存业务语义和实现规格，代码保存真实实现，Git 历史追溯变更；根 `AGENTS.md` 约束 agent 如何使用这些来源。`norn-governance/plans/` 只承接未完成任务的短期状态，不是第四种权威来源。

主实现规格是项目骨骼，代码是项目皮肤和血肉。规格保存换语言、框架或代码结构后仍需保持的目标、流程、边界、规则、失败处理和验收；当前机制与调用细节留在代码中。实现和审阅时都要检查规格是否落后，并把稳定结论回写到正确的长期来源。

## 能力

统一使用 `$norn-governance`：

- 初始化：为空项目创建当前 Norn 治理结构。
- 迁移：识别旧 `docs/` 治理文件并迁移到 `norn-governance/`，保留项目自己的其他文档。
- 升级：更新 Norn 管理的通用规则，同时保留主规格和受管区块外的项目内容。

Skill 会先只读分析并展示逐文件计划。写入、迁移或删除只在用户确认后执行；归属不明、目标路径冲突或修改过的受管区块需要单独选择。用户不需要手工运行内部脚本。

例如：

```text
使用 $norn-governance 初始化当前项目
使用 $norn-governance 把旧治理结构迁移到 Norn
使用 $norn-governance 更新当前项目的治理规则
```

## 治理模型

初始化后的固定结构为：

```text
AGENTS.md
norn-governance/
  .norn.json
  AGENTS.md
  spec/
    AGENTS.md
    main-spec.md
  appendix/
    README.md
```

`main-spec.md` 初始化后归项目所有，后续升级不会使用模板覆盖。四个通用 Markdown 治理文件通过稳定的 `norn:managed` 区块区分 Norn 规则和项目扩展：基线未修改时可自动升级，基线已修改时由用户选择保留、采用新版或语义融合。`.norn.json` 只记录模板版本、所有权和区块基线哈希，不是人类规格。

旧版迁移只处理确认属于 Norn 的以下映射：

```text
docs/AGENTS.md                 -> norn-governance/AGENTS.md
docs/spec/AGENTS.md            -> norn-governance/spec/AGENTS.md
docs/spec/main-spec.md         -> norn-governance/spec/main-spec.md
docs/appendix/README.md        -> norn-governance/appendix/README.md
```

只出现同名路径不足以证明文件归 Norn 所有。目标内容写入并校验成功前不会删除旧文件，旧目录也只在完全为空时清理。

## 短期计划

`norn-governance/plans/` 不在固定初始化清单中。只有任务需要暂停、跨会话或跨设备继续时，才按需保存简短恢复计划；它只记录意图、状态、相对路径、选择、未决冲突、风险和重新分析规则，不保存文件正文、临时产物路径或可复用授权。任务完成或取消后删除计划。

## 仓库结构

```text
template/                         # 当前治理模板
skills/norn-governance/
  SKILL.md                        # 用户意图与交互编排
  agents/openai.yaml              # Codex UI 元数据
  references/recovery-plans.md    # 按需加载的跨会话规则
  scripts/                        # 确定性分析、解析和执行引擎
  assets/
    ai-project-governance-template/
    legacy-templates/
  tests/
norn-governance/spec/main-spec.md # 本项目的实现规格
```

仓库内 `skills/norn-governance/` 是 canonical 源码。本机 Codex 安装副本位于 `~/.codex/skills/norn-governance/`；变更必须先在仓库中验证，再同步安装副本。

Norn 不自动提交、推送、创建分支、修改 Git 配置，也不迁移任意项目文档或尝试通用 Markdown 自动合并。
