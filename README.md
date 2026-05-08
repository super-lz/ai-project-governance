# AI Project Governance

一套可复制到项目仓库里的 AI 工程化治理模板。

它把 AI 协作中的长期依据收敛到少数稳定文件：根目录 `AGENTS.md` 负责执行规则，`docs/spec/` 负责主实现规格，代码和 Git 历史负责记录真实实现与变更。

## 目录

```text
template/
  AGENTS.md
  docs/
    AGENTS.md
    spec/
      AGENTS.md
      main-spec.md
    appendix/
      README.md
```

## 使用

1. 将 `template/AGENTS.md` 和 `template/docs/` 复制到目标项目根目录。
2. 按项目情况修改 `docs/spec/main-spec.md`，必要时重命名为具体业务规格。
3. 后续让 AI 按项目内 `AGENTS.md` 工作。

具体执行流程、文档维护规则和规格边界都在模板文件中定义。
