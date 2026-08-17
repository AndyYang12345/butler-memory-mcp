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

Butler 分层记忆的 **MCP 桥**：把 ai-butler-framework 的
`MemoryService` / `LayeredMemoryService` 以标准 MCP 工具暴露给任何 MCP 客户端
（DSH、Claude Code、Codex 等），同时提供一个仅限 loopback 的 HTTP API 供
DSH Web 面板（`dsh-butler-memory`）读取。

```text
DSH agent ──(MCP stdio)──► ai-butler-memory-mcp ──► MemoryService ──► PostgreSQL
DSH web 面板 ──(插件托管 stdio)──► 同一进程、同一 principal
```

## 自包含分发（vendored）

本包**运行时零依赖 ai-butler-framework**：所需的记忆领域代码
（`MemoryService`/`LayeredMemoryService`/ORM 模型/数据库与配置辅助）以
vendoring 方式内置于 `ai_butler_memory_mcp/vendored/`，归属校验、敏感度上限、
revision 乐观锁、审计与证据同事务等语义与上游**逐字一致**。上游文件清单、
行号区间与漂移检查见 [VENDORED.md](VENDORED.md)（`scripts/check-vendored.py`）。

Schema 迁移仍由 ai-butler-framework 的部署负责（`ai-butler-db upgrade`）；
本包只连接已有数据库，不创建、不修改 schema。

## 安装

### 从 PyPI（发布后推荐）

```bash
pip install butler-memory-mcp
```

### 本地开发（源码 checkout）

```bash
cd butler-memory-mcp && python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

## 首次初始化（自举，无需 ai-butler-framework）

### 方式一：一键起库（推荐，Docker 用户）

前提：已安装并启动 Docker（Windows/macOS 为 Docker Desktop）。

```bash
ai-butler-memory-mcp setup-docker
```

这一条命令完成全部部署：创建/复用 PostgreSQL 容器 → 等待就绪 → 写入
`~/.config/butler-memory-mcp/.env`（自动生成密码，权限 600）→ 建 schema →
创建属主用户与桥设备并打印一次性 token。可重复执行（幂等：容器已运行则
复用，身份已配置则跳过）。

常用参数：`--container-name`（默认 `ai-butler-pg`）、`--port`（默认 5432）、
`--password`（新容器密码，缺省自动生成）、`--user-name`/`--device-name`/
`--scope`。

### 方式二：已有 PostgreSQL（三步手动）

```bash
# 1. 建表（对已迁移的库是安全 no-op，只建缺失表）
ai-butler-memory-mcp initdb

# 2. 创建属主用户与桥设备（token 只显示一次）
ai-butler-memory-mcp admin bootstrap \
  --user-name 博士 --device-name dsh-agent --device-kind agent \
  --scope memory:read --scope memory:write
# 输出 user_id / device_id / device_token

# 3. 把 user_id / device_id 填进配置
```

## 配置

把环境配置放进 `~/.config/butler-memory-mcp/.env`（DSH 的 stdio 桥会清洗
疑似凭据的环境变量，env 文件是可靠通道；`setup-docker` 会自动生成它）：

```dotenv
AI_BUTLER_DATABASE_URL=postgresql+asyncpg://ai_butler:密码@127.0.0.1:5432/ai_butler
AI_BUTLER_MCP_USER_ID=<bootstrap 输出的 user_id>
AI_BUTLER_MCP_DEVICE_ID=<bootstrap 输出的 device_id>
```

**与 ai-butler-framework 共用同一数据库**的部署无需 initdb/bootstrap：
沿用框架的 `ai-butler-db upgrade` 迁移和 `ai-butler-admin add-device` 注册，
把打印的 `user_id`/`device_id` 填进上面两个变量即可。

写操作只有在这台设备真实属于该用户时才会被接受——身份与审计不因
MCP 而放松。

## 运行

```bash
ai-butler-memory-mcp                       # stdio MCP（给 agent 用，DSH 会自动 spawn）
ai-butler-memory-mcp --transport http --port 8771   # 面板 API（0.1.2+ 的 DSH 插件已不需要）
```

## 暴露的工具（DSH 中为 mcp__butler__memory_*）

| 工具 | 语义 | 敏感度 |
|---|---|---|
| `memory_list` / `memory_search` | 列出/检索记忆（search 自动排除 private/secret） | internal 封顶 |
| `memory_revisions` | 不可变修订历史 | — |
| `memory_create` / `memory_revise` / `memory_archive` | 显式写入，revision 绑定 | public/internal 封顶 |
| `memory_candidates` / `memory_candidate_accept` / `memory_candidate_reject` | 推断候选，绝不静默入库 | — |

## 当前边界（v0.2 刻意取舍）

- **无浏览器式强确认**：MCP 写入依赖工具描述约束（"仅当用户明确要求"）+ 敏感度
  封顶，不等于框架 Web 端的 L2 确认卡片。后续可接 DSH `ask-user`。
- **仅 loopback**：HTTP 面板 API 拒绝非 loopback 绑定；stdio 模式不监听端口。
- **单用户单设备 principal**：多用户映射属后续设计（见 PLAN.md）。
- 数据 durable 但**备份/恢复尚未实现**（框架 P9 未完成），发布说明中需如实标注。

## 测试

```bash
.venv/bin/pytest     # 离线协议测试；vendored 领域代码与上游逐字一致
.venv/bin/python scripts/check-vendored.py --upstream ../ai-butler-framework   # 漂移检查
```

## License

[Apache License 2.0](LICENSE)，与上游 ai-butler-framework 一致。本项目不包含
任何专有模型或素材；发布衍生作品时请保留许可与署名要求。

## 相关项目

- `ai-butler-framework` — 记忆领域服务的上游实现方（owner/revision/audit
  语义的权威来源；本包 vendoring 其记忆领域代码并做漂移检查）；
- [dsh-butler-memory](https://github.com/AndyYang12345/dsh-butler-memory) —
  DeepSeek Harness 接入组合包：agent 工具 + Web 记忆面板。
