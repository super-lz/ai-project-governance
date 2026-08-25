# 跨会话恢复计划

恢复计划只保存未完成治理任务的短期执行上下文，帮助另一会话或设备重新理解意图；它不是实现规格、机器执行计划或长期历史。

## 创建条件

只有用户明确需要暂停、跨会话或跨设备继续时，才创建：

```text
norn-governance/plans/YYYY-MM-DD-<slug>.md
```

按需创建 `plans/`，不创建 README、索引、归档或占位文件。普通单会话工作继续使用系统临时目录中的 `plan.json` 和渲染产物。

## 安全格式

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

只记录意图、上次观察状态、相对治理路径、已确认语义选择、未决冲突、风险和重新分析规则。不要写入：

- 文件正文、密钥或其他敏感信息；
- 绝对临时路径、机器计划路径或渲染产物路径；
- 可复用的执行授权、旧计划摘要或可直接执行的命令。

## 恢复与清理

恢复时即使仍在同一设备，也必须重新运行只读分析，比较新的动作摘要并取得新的执行确认。文件指纹、动作或冲突变化时，丢弃旧机器计划并解释差异；恢复计划中的既有选择只能作为讨论上下文，不能代替当前确认。

任务完成或用户取消后删除恢复计划。只有用户明确要求提交时才可提交该临时文件；完成后的计划不得作为归档或索引保留。
