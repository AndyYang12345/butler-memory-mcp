# Vendored Code（自包含分发的同步治理）

本包通过 **vendoring** 内置 Butler Framework 的记忆领域代码，从而**不依赖
`ai-butler-framework` 包**即可运行（该包未发布到 PyPI，且包含 agent runtime
等本桥不需要的部分）。

## 清单与提取方式

| vendored 文件 | 上游文件 | 提取方式 |
|---|---|---|
| `vendored/models.py` | `src/ai_butler_runtime/persistence/models.py` | **全文复制**（纯 SQLAlchemy + stdlib，无内部 import） |
| `vendored/database.py` | `src/ai_butler_runtime/persistence/database.py` | 全文复制，仅 `..config` → `.config` 一处 import 重写 |
| `vendored/config.py` | `src/ai_butler_runtime/config.py` | 前缀切片（第 1–98 行：`ConfigurationError` + `load_dotenv`） |
| `vendored/credentials.py` | `src/ai_butler_runtime/persistence/credentials.py` | **全文复制**（零内部依赖） |
| `vendored/timezone.py` | `src/ai_butler_runtime/timezone.py` | **全文复制**（零内部依赖） |
| `vendored/memory_policy.py` | `src/ai_butler_runtime/memory_policy.py` | 提取：第 23–32 行（`_SPACE`/`_SECRET`/`_PRIVATE`）+ 第 48–97 行（`_SYNONYMS`…`ExtractedMemory`）+ 第 367–423 行（`LocalSemanticEncoder`/`recent_decay`），imports 重写 |
| `vendored/memory_service.py` | `src/ai_butler_runtime/persistence/services.py` | 提取：异常子集 + 第 222–292 行（`_clean_text`/`_audit`/`_ensure_device_owner`）+ 第 3374–3730 行（`MemoryService`），imports 重写 |
| `vendored/layered_memory.py` | `src/ai_butler_runtime/persistence/memory_services.py` | 提取：第 75–617 行（`_audit`…`LayeredMemoryService` 结束），imports 重写 |
| `vendored/identity.py` | `src/ai_butler_runtime/persistence/services.py` | AST 提取：`_SCOPE`/`DEFAULT_DEVICE_SCOPES`（88–100）、`_validated_scopes`（226–230）、`BootstrapResult`（141–150）、`IdentityService.__init__`+`bootstrap`+`add_device`（292–458），imports 重写 |
| `vendored/serializers.py` | `src/ai_butler_runtime/memory_tools.py` | 提取两个函数并精简 imports |

表名、列名、语义与上游完全一致（连同一数据库）。schema 初始化有两条路径：
**纯 MCP 部署**用 `ai-butler-memory-mcp initdb`（vendored 模型 `create_all`，
无 Alembic 历史）；**与框架共用同一库**时仍由框架的 `ai-butler-db upgrade`
负责迁移（两者对已存在的表都安全）。

## 漂移检查

```bash
python scripts/check-vendored.py --upstream /path/to/ai-butler-framework
```

脚本对三个机械复制文件做精确对比，对四个提取文件比较"上游区间 SHA-256"
与记录基线，任一变化即报告漂移并要求重新同步。

## 同步步骤（上游更新后）

1. 运行漂移检查确认变化范围；
2. 按上表重新执行提取（注意行号随上游变化，需先 `grep` 定位新边界）；
3. `python -m py_compile src/ai_butler_memory_mcp/vendored/*.py`；
4. 跑离线测试 + 真实数据库回归（`memory_list`/`memory_search`/候选链路）；
5. 更新本文件的基线与 `scripts/check-vendored.py` 中的 SHA-256 记录；
6. 提交并注明同步的上游 commit。

## 底线

- 任何行为差异都以**上游实现为准**，同步时不做"顺手改进"；
- vendored 代码禁止在本仓库内单独修改逻辑（只允许 import 适配），
  否则漂移检查与审计语义会失真。
