# Norn Governance 实现规格

## 目标

Norn Governance 为 AI 协作项目提供可初始化、可迁移、可升级的治理生命周期。用户只与 `$norn-governance` skill 交互；内部脚本负责生成可验证的操作计划并在用户确认后执行，不要求用户理解或手工运行命令。

完成后的用户结果是：

- 新项目可以获得当前 Norn 治理结构。
- 使用旧 `docs/` 治理结构的项目可以安全迁移到 `norn-governance/`。
- 已采用 Norn 的项目可以升级通用治理规则，同时保留项目规格和项目定制内容。
- 任一时刻只保留一个权威规格路径，项目自己的其他 `docs/` 内容不受影响。
- 迁移和升级始终先展示计划、再由用户确认，不静默移动、覆盖或删除文件。

## 名称与兼容边界

Canonical skill 名称、目录和调用标识统一为：

```text
skills/norn-governance/
$norn-governance
scripts/manage_norn_governance.py
~/.codex/skills/norn-governance/
```

旧 `init-ai-project` 名称硬切换删除，不保留别名、兼容 skill 或旧脚本入口。README、UI 元数据、测试、模板引用和本机安装副本必须同步更新。

## 治理结构

新项目的受管结构为：

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

`norn-governance/plans/` 仍按任务需要创建，不放入固定初始化文件，不创建 README、索引或占位文件。

## 用户交互

用户通过自然语言表达意图，例如：

```text
使用 $norn-governance 初始化当前项目
使用 $norn-governance 更新当前项目
使用 $norn-governance 把旧治理结构迁移到 Norn
```

Skill 根据项目状态选择初始化、升级或迁移。用户请求初始化但项目已有旧治理结构时，必须转为迁移分析，不得创建第二套治理文件。

每次可能写入、移动或删除文件的操作都遵循：

1. 只读分析项目状态。
2. 生成逐文件操作计划。
3. 用自然语言向用户说明移动、融合、保留、删除、冲突和风险。
4. 用户确认一次后执行所有无歧义操作；归属或内容仍有歧义的文件必须单独确认。
5. 执行后验证内容、路径、版本和 Git 差异。

内部脚本和参数属于实现细节，不把命令操作转嫁给用户。Skill 不自动提交、推送或修改 Git 配置。

## 组件与职责

### Skill 编排层

`SKILL.md` 负责：

- 理解用户意图和目标仓库。
- 调用分析器并解释报告。
- 对语义归属、项目定制和冲突方案做上下文判断。
- 在执行前取得用户确认。
- 调用执行器并汇报最终结果。

### 确定性执行层

`manage_norn_governance.py` 负责：

- 读取固定受管路径和文件内容。
- 计算 SHA-256 指纹。
- 分类项目状态和逐文件动作。
- 生成机器可读计划。
- 校验计划前置条件。
- 按已确认计划创建、移动、融合和清理文件。
- 验证迁移后的不变量。

脚本不自行判断产品取舍，不对任意 Markdown 做猜测式合并。

## 项目状态分类

分析器必须把项目归为以下状态之一：

- `uninitialized`：不存在 Norn 或可识别的旧治理结构。
- `current`：存在有效 `.norn.json`，结构和模板版本均为当前版本。
- `upgradeable`：存在有效 Norn 元数据，但模板版本落后。
- `legacy`：旧 `docs/` 治理结构归属明确，尚未迁移。
- `mixed`：新旧治理路径并存，需要去重、合并或完成未结束迁移。
- `ambiguous`：存在同名文件，但证据不足以确认由 Norn 管理。
- `conflict`：目标路径、受管区块、文件类型或内容发生无法自动解决的冲突。

## 操作计划

分析结果必须为每个受影响路径产生下列动作之一：

- `create`
- `move`
- `merge`
- `delete`
- `keep`
- `conflict`

计划至少记录：

- 源路径和目标路径。
- 当前内容 SHA-256；路径不存在时显式记录不存在状态。
- 文件归属及判断证据。
- 计划生成的目标内容哈希。
- 动作原因、风险和验证条件。
- 完整计划摘要哈希。

执行阶段必须重新计算所有前置条件。用户确认后任一受影响文件发生变化，整个计划失效并重新分析，不执行部分旧计划。

机器可读计划默认保存在系统临时目录，不进入仓库。只有迁移任务需要跨会话或跨设备恢复时，Skill 才按 Norn 计划规则在 `norn-governance/plans/` 保存不含文件正文和敏感信息的简短恢复计划；任务完成或取消后删除。

## 旧治理归属识别

旧路径固定映射为：

```text
docs/AGENTS.md
→ norn-governance/AGENTS.md

docs/spec/AGENTS.md
→ norn-governance/spec/AGENTS.md

docs/spec/main-spec.md
→ norn-governance/spec/main-spec.md

docs/appendix/README.md
→ norn-governance/appendix/README.md
```

根 `AGENTS.md` 不移动，只升级受管规则和治理路径引用。

满足以下任一条件时，可以确认文件属于旧 Norn：

- 内容哈希与 skill 内已知旧模板版本匹配。
- 旧治理结构形成互相印证的完整证据链：根 `AGENTS.md` 引用旧治理入口和主规格；`docs/AGENTS.md` 定义 `spec/` 与 `appendix/` 职责；`docs/spec/AGENTS.md` 声明 `main-spec.md` 的权威性。

只有孤立同名路径、缺少治理引用或文件同时承担其他文档职责时，归类为 `ambiguous`。不能仅凭存在 `docs/spec/main-spec.md` 就认定它属于 Norn。

## 文件所有权

### Norn 管理

- 根 `AGENTS.md` 中带稳定标识的通用治理区块。
- `norn-governance/AGENTS.md` 的通用治理区块。
- `norn-governance/spec/AGENTS.md` 的通用治理区块。
- `norn-governance/appendix/README.md` 的通用治理区块。
- `norn-governance/.norn.json`。

### 项目管理

- `norn-governance/spec/main-spec.md`。
- `norn-governance/plans/` 下的进行中计划。
- 项目自行新增的规格、附录和治理扩展内容。

`main-spec.md` 只在首次初始化时提供起始模板。一旦进入项目，Norn 后续升级永远不得用新模板覆盖它。

## 版本与受管区块

`.norn.json` 是机器元数据，不作为实现规格或人类说明。首个正式格式使用：

```json
{
  "schema_version": 1,
  "template_version": 1,
  "managed_files": {}
}
```

`managed_files` 为每个受管文件记录：

- 所有权类型：`managed`、`mixed` 或 `project`。
- 上次应用的模板基线 SHA-256。
- 受管区块稳定标识。
- 上次成功升级的模板版本。

通用治理内容使用稳定的 Markdown 注释边界，例如：

```markdown
<!-- norn:managed:start core-governance -->
...
<!-- norn:managed:end core-governance -->
```

项目专属规则写在受管区块外。后续升级只替换未被项目修改的受管区块：

- 当前区块与记录基线一致：自动升级。
- 当前区块已经被修改：生成冲突，由用户选择保留、采用新版或语义融合。
- 区块外内容：始终保留。

旧项目第一次迁移时没有元数据和区块标记。Skill 必须先完成归属判断与语义融合，成功后再加入标记并写入 `.norn.json`。

## 迁移与融合规则

- 迁移和升级在同一份用户确认计划中完成，但动作必须分开展示。
- `main-spec.md` 保留全部业务内容，只更新能够确定属于 Norn 治理路径的引用。
- 治理入口先保留项目定制，再融合当前模板中的计划生命周期、整体性与变更边界等规则。
- 新旧文件内容相同时，保留新路径并删除旧副本。
- 新路径已存在且内容不同时，不覆盖；进入语义合并或冲突选择。
- 项目的其他 `docs/` 文件和目录永远不移动。
- 旧文件只有在新路径内容写入并校验成功后才能删除。
- `docs/spec/`、`docs/appendix/` 和 `docs/` 只在完全为空时删除目录。
- 迁移结束后不得长期保留两套权威规格。

## 执行安全与恢复

执行器按以下顺序工作：

1. 重新校验计划摘要和所有路径指纹。
2. 在临时目录生成全部目标内容。
3. 验证 Markdown、受管区块、元数据和规格内容不变量。
4. 通过临时文件与原子替换写入目标文件。
5. 校验目标路径实际字节与计划一致。
6. 删除已经成功迁移且有目标副本的旧文件。
7. 删除已经为空的旧目录。
8. 最后写入 `.norn.json` 作为本次升级成功标记。

任一步失败都停止后续动作。源文件在对应目标校验成功前不得删除。中断后再次分析必须识别 `mixed` 状态，并能继续完成或给出恢复建议，不假定上一次操作完整成功。

## 验证与验收

自动化测试至少覆盖：

- 空项目初始化为当前 Norn 结构。
- 完整旧模板迁移。
- 深度修改的 `main-spec.md` 保留业务内容。
- 孤立同名文件被判定为归属不明。
- `docs/` 中其他文件完全保留。
- 新路径不存在、内容相同、内容冲突三种情况。
- 根 `AGENTS.md` 项目扩展内容保留。
- 用户确认后文件发生变化时拒绝执行。
- 中途写入或校验失败时不删除旧文件。
- 重复执行保持幂等。
- 未修改的受管区块自动升级。
- 修改过的受管区块进入冲突确认。
- 迁移后只保留一个权威规格路径。
- 计划区和整体性治理规则进入迁移后的入口。
- 仓库模板、skill 资产和本机安装副本一致。

验收命令必须包含单元测试、skill 结构校验、模板资产比较和真实临时项目迁移。最终工作树差异必须只包含已确认范围。

## 非目标

- 不迁移项目任意 `docs/` 文档。
- 不为任意 Markdown 提供通用自动合并器。
- 不覆盖项目主实现规格。
- 不静默解决修改过的受管区块冲突。
- 不创建计划归档、计划索引或空计划目录。
- 不自动提交、推送、创建分支或修改 Git 配置。
- 不保留 `init-ai-project` 兼容入口。
- 不在本次能力中加入 Flutter 项目初始化。
