# butler-memory-mcp

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-stdio-brightgreen)](https://modelcontextprotocol.io)

> **给你的 AI agent 一份真正属于你的长期记忆。** 一个 MCP 服务器，把你明确要求
> 记住的事实、偏好和项目上下文写入**你自己的 PostgreSQL**——每次写入带修订历史
> 与审计证据，检索自动按敏感度过滤。模型不能静默写入；推断出的东西只会变成
> 等你决定的候选。接任何 MCP 客户端即用。

## 仓库简介

> Layered long-term memory for AI agents as an MCP server — PostgreSQL-backed,
> versioned, audited. Agents remember only what you explicitly asked.

Butler 分层记忆的 **MCP 桥**：把 [ai-butler-framework](../ai-butler-framework) 的
`MemoryService` / `LayeredMemoryService` 以标准 MCP 工具暴露给任何 MCP 客户端
（DSH、Claude Code、Codex 等），同时提供一个仅限 loopback 的 HTTP API 供
DSH Web 面板（`dsh-butler-memory`）读取。

```text
DSH agent ──(MCP stdio)──► ai-butler-memory-mcp ──► MemoryService ──► PostgreSQL
DSH web 面板 ──(HTTP 127.0.0.1:8771)──► 同一进程、同一 principal
```

## 为什么是"桥"而不是重写

本包**不含任何记忆业务逻辑**。归属校验、敏感度上限、revision 乐观锁、
审计与证据同事务、Schema 迁移全部继承自框架，本包只做协议映射与错误翻译。

## 安装

### 从 PyPI（发布后推荐）

```bash
pip install butler-memory-mcp
```

前置：`ai-butler-framework` 已发布到 PyPI（本包声明
`ai-butler-framework>=0.1` 依赖）。

### 本地开发（源码 checkout）

```bash
cd ai-butler-framework && .venv/bin/pip install -e .     # 先装框架（本地开发）
cd ../butler-memory-mcp && python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

## 配置

复制 `.env.example` 为 `.env`，填三个值：

1. `AI_BUTLER_DATABASE_URL` — 与框架共用的 PostgreSQL；
2. `AI_BUTLER_MCP_USER_ID` — 记忆属主（`ai-butler-admin bootstrap` 输出）；
3. `AI_BUTLER_MCP_DEVICE_ID` — 桥作为该用户的一台**持久设备**：

```bash
.venv/bin/ai-butler-admin add-device \
  --user-id <USER_UUID> \
  --device-name dsh-agent --device-kind agent \
  --scope memory:read --scope memory:write
```

写操作只有在这台设备真实属于该用户时才会被框架接受——身份与审计不因
MCP 而放松。

## 运行

```bash
.venv/bin/ai-butler-memory-mcp                # stdio MCP（给 agent 用）
.venv/bin/ai-butler-memory-mcp --transport http --port 8771   # 面板 API
```

## 暴露的工具（DSH 中为 mcp__butler__memory_*）

| 工具 | 语义 | 敏感度 |
|---|---|---|
| `memory_list` / `memory_search` | 列出/检索记忆（search 自动排除 private/secret） | internal 封顶 |
| `memory_revisions` | 不可变修订历史 | — |
| `memory_create` / `memory_revise` / `memory_archive` | 显式写入，revision 绑定 | public/internal 封顶 |
| `memory_candidates` / `memory_candidate_accept` / `memory_candidate_reject` | 推断候选，绝不静默入库 | — |

## 当前边界（v0.1 刻意取舍）

- **无浏览器式强确认**：MCP 写入依赖工具描述约束（"仅当用户明确要求"）+ 敏感度
  封顶，不等于框架 Web 端的 L2 确认卡片。后续可接 DSH `ask-user`。
- **仅 loopback**：HTTP 面板 API 拒绝非 loopback 绑定；stdio 模式不监听端口。
- **单用户单设备 principal**：多用户映射属后续设计（见 PLAN.md）。
- 数据 durable 但**备份/恢复尚未实现**（框架 P9 未完成），发布说明中需如实标注。

## 测试

```bash
.venv/bin/pytest     # 离线协议测试；领域行为由框架自身测试覆盖
```

## License

[Apache License 2.0](LICENSE)，与上游 ai-butler-framework 一致。本项目不包含
任何专有模型或素材；发布衍生作品时请保留许可与署名要求。

## 相关项目

- `ai-butler-framework` — 记忆领域服务的实现方（owner/revision/audit 语义的
  权威来源，本包通过 `ai-butler-framework` 依赖直接调用其服务层）；
- [dsh-butler-memory](https://github.com/AndyYang12345/dsh-butler-memory) —
  DeepSeek Harness 接入组合包：agent 工具 + Web 记忆面板。
