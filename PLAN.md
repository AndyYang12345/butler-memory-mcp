# butler-memory-mcp 移植规划与实施步骤

> 状态：P0 已落地（本仓库骨架）；P1-P3 为后续切片。
> 上游：`ai-butler-framework`（/home/harekasa/ai-butler-framework）

## 1. 目标与非目标

**目标**：把框架的分层记忆能力以标准 MCP 暴露给外部 agent（DSH 等），并给
DSH Web 面板一个 loopback 数据源，**零业务逻辑重写**。

**非目标**（v0.1）：

- 不做多用户/多租户映射（单 principal）；
- 不复制 L2 确认卡片流程（由工具描述 + 敏感度封顶约束）；
- 不做备份恢复、公网监听、多进程协调（属框架 P9/P10）；
- 不把 Persona 字段塞进通用记忆工具（框架已明确禁止）。

## 2. 复用映射（porting map）

| 框架文件 | 本仓库用途 |
|---|---|
| `src/ai_butler_runtime/persistence/services.py::MemoryService` | 直接调用：list/search/revisions/create/revise/archive |
| `src/ai_butler_runtime/persistence/memory_services.py::LayeredMemoryService` | 直接调用：candidates 列表/接受/拒绝 |
| `src/ai_butler_runtime/persistence/database.py::Database/Config` | 连接、事务、readiness 语义原样复用 |
| `src/ai_butler_runtime/config.py::load_dotenv/ConfigurationError` | 配置加载与错误风格一致 |
| `src/ai_butler_runtime/memory_tools.py::memory_output/memory_revision_output` | 输出序列化原样复用（跨端一致） |
| `src/ai_butler_runtime/mcp_client.py` | **风格参照**：零依赖 JSON-RPC 手写（本仓库 `mcp_server.py`） |
| `src/ai_butler_runtime/persistence/models.py` | 不复制；通过框架包导入 |
| `web/index.html + app.js` 记忆面板 | 不复制代码；面板语义移植到 `dsh-butler-memory` |

## 3. 阶段与步骤

### P0 — 协议桥（本仓库已落地）

1. `config.py`：数据库 + 单 principal（user/device UUID）环境配置；
2. `operations.py`：9 个操作全部走 `MemoryService`/`LayeredMemoryService`，
   错误翻译为 `BridgeError` 稳定码（resource_not_found / revision_conflict /
   memory_access_denied / invalid_request）；
3. `mcp_server.py`：零依赖 stdio JSON-RPC（initialize 版本协商 / ping /
   notifications / tools/list / tools/call），stdout 只承载协议；
4. `http_api.py`：面板只读 API（list/search/revisions + candidates
   accept/reject），**不含 create/revise/archive**；
5. 测试：协议层离线测试（`tests/test_mcp_server.py`）。

验收：`pytest` 通过；`echo initialize... | ai-butler-memory-mcp` 手测一轮
initialize/tools/list。

### P1 — 真实数据库联调

1. `docker compose up -d postgres` + `ai-butler-db upgrade`；
2. `ai-butler-admin bootstrap` 建用户，`add-device` 建 dsh-agent 设备；
3. 填 `.env`，跑 `--transport stdio`，用 `printf` 发 `tools/call` 验证
   memory_create → memory_search → memory_revise(revision 冲突) → archive；
4. 跑 `--transport http`，curl 六个端点；确认非 loopback 绑定被拒。

验收：真实 PG 上走通写→搜→改→归档全链路；revision 冲突返回
`revision_conflict`；设备不属于用户时写操作被框架拒绝。

### P2 — 接入 DSH（配合 dsh-butler-memory）

1. `dsh plugin add ../dsh-butler-memory`（或 `--patch` 本地 yml）；
2. 验证 `mcp__butler__memory_*` 工具出现、跨会话召回成功（官方
   examples/mcp-memory 的验证流程照搬）；
3. 验证 Web 面板按钮与列表、候选 accept/reject。

验收：DSH 会话 A 写入 → 会话 B 召回；面板刷新可见；候选接受后成为长期记忆。

### P3 — 发布与加固

1. 上游 `ai-butler-framework` 发布 PyPI 后，本包声明正式依赖并发布；
2. 补 DSH `ask-user` 确认对接（写操作前弹确认）作为可选开关；
3. 等待框架 P9 备份/轮换后补迁移与恢复演练说明；
4. 商标/命名检查（"ai-butler" 为临时名，见上游 README Naming status）。

## 4. 风险与已定边界

| 风险 | 处理 |
|---|---|
| MCP 写入无浏览器级确认 | 工具描述硬约束 + public/internal 封顶 + 审计留痕；P3 接 ask-user |
| 单 principal 被多个客户端共享 | v0.1 定位单用户本机；多映射需框架侧"凭据→principal"设计 |
| 框架 schema 升级 | 本包 pin `ai-butler-framework>=0.1`，运行前框架 readiness 校验 head |
| 面板 HTTP 无认证 | 仅 loopback 绑定 + 只读 + 候选决定；公网形态留到框架 P10 |
