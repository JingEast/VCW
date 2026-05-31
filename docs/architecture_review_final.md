# VCW 架构升级最终审查报告

**审查日期**: 2026-05-31  
**审查范围**: app/, vcw_copywriter/, llm/, prompt_runtime/, domains/, services/  
**审查维度**: 循环依赖、领域泄漏、应用层依赖、Routes 业务化、Service 膨胀、Repository 泄漏、LLM 耦合、水平扩展、事务边界、微服务拆分

---

## 1. 架构评分

| 维度 | 得分 | 权重 | 加权分 | 关键问题 |
|------|------|------|--------|----------|
| 循环依赖 | 7/10 | 1.0 | 7.0 | `wsgi.py` 与 `app/` 包无冲突；`domains.editor.application` 反向依赖 `services` |
| 领域泄漏 | 4/10 | 1.5 | 6.0 | 实体直接继承 SQLAlchemy Base；Generator/ModelRouter 直接调用 OpenAI SDK |
| 应用层依赖基础设施 | 5/10 | 1.5 | 7.5 | `GenerationService` 直接导入 Celery/ORM；`SchedulerService` 直接实例化 Scraper |
| Routes 业务化 | 6/10 | 1.0 | 6.0 | Config/Memory Routes 包含表单解析与数据结构操作 |
| Service 膨胀 | 4/10 | 1.5 | 6.0 | `GenerationService` 上帝类（~560 行）；`TrendDatabase`/`MemoryBank` 混合 3 种职责 |
| Repository ORM 泄漏 | 4/10 | 1.5 | 6.0 | Repository 返回 ORM 对象；`GenerationService` 绕过 Repository 直接 query |
| LLM Provider 耦合 | 3/10 | 1.5 | 4.5 | **新建的 `llm/` adapter 层完全未被生产代码使用**；旧代码硬编码 OpenAI SDK |
| 水平扩展 | 4/10 | 1.5 | 6.0 | `MemoryBank`/`TrendDatabase`/`EditorWorkflow` 持有进程内内存状态 |
| 事务边界 | 3/10 | 1.5 | 4.5 | `TransactionManager.atomic()` 无真实事务；补偿异常静默吞掉 |
| 微服务拆分 | 4/10 | 1.0 | 4.0 | `EditorService` 直接同步调用 `GenerationService`；无跨服务调用抽象 |

**总分: 57.5 / 100**（加权平均）

**评级: C+** — 架构分层意识存在，但基础设施泄漏严重，新架构投资（`llm/`, `domains/`）与生产代码脱节。

---

## 2. 风险等级矩阵

### 🔴 CRITICAL（不修复不可投产）

| # | 风险项 | 影响 | 修复优先级 |
|---|--------|------|------------|
| C1 | `app.py` 与 `app/` 包名冲突 | 任何 `import app` 可能解析为 `app.py` 模块而非 `app/` 包，导致 `ImportError` | P0 |
| C2 | **`llm/` adapter 层完全未接入生产代码** | 新架构投资成为"写即弃"代码；新增 provider 仍需修改 `generator.py`/`model_router.py` | P0 |
| C3 | `TransactionManager.atomic()` 是假的 | 无真实 DB 事务，只有 LIFO 补偿队列；补偿失败静默吞异常；文件与 DB 状态不一致 | P0 |

### 🟠 HIGH（严重影响可维护性与扩展性）

| # | 风险项 | 影响 |
|---|--------|------|
| H1 | `vcw_copywriter/db/models.py` 实体直接继承 SQLAlchemy `Base` | 领域层被 ORM 污染；无法独立于数据库测试；无法切换 ORM |
| H2 | `generator.py` / `model_router.py` 直接调用 OpenAI SDK | 无法接入 Anthropic/Gemini 原生 API；Kimi/DeepSeek 靠运行时 workaround |
| H3 | `MemoryBank` 持有进程内 `self.data` + `_vector_search` | 多 Worker 状态不共享；向量索引 divergence；写操作不可见 |
| H4 | `TrendDatabase` 持有进程内 `self.data` + JSON cache | 同 H3；并发爬虫时数据竞争 |
| H5 | `EditorWorkflow.index` 是内存中的文件索引 | 多 Worker 文件写竞争；无文件锁（或锁实现不完整） |
| H6 | `ModelRouter.EndpointStatus` 是进程内计数器 | Worker A 禁用 endpoint，Worker B 仍发流量；无共享健康状态 |
| H7 | `GenerationService` 是上帝类（~560 行） | 混合 prompt/LLM/quality/file/async/batch 6 种职责；单点修改风险极高 |
| H8 | Repository 返回 ORM 对象（`Trend`, `MemoryEntry`, `GenerationJob`） | 调用者拿到 SQLAlchemy 代理对象，触发 lazy loading；领域层与 ORM 绑定 |

### 🟡 MEDIUM（影响代码清晰度与演进速度）

| # | 风险项 | 影响 |
|---|--------|------|
| M1 | `domains/editor/application` 反向导入 `services.editor_service` | Application 层依赖 Service 层，违反依赖方向；一旦 Service 回引即产生循环 |
| M2 | `app/pages/config.py` 包含复杂表单解析与验证 | Route 层承担了 application 层职责 |
| M3 | `app/pages/memory.py` 直接操作 `memory_bank.data["entries"]` | Route 层触及领域对象内部结构，调用私有方法 `_save()` |
| M4 | DI Container 是 God Object（~430 行） | 知道所有具体实现；提取微服务时需重写工厂子集 |
| M5 | `prompt_runtime/__init__.py` / `services/__init__.py` eager re-export | 增大导入表面积；未来任意交叉导入即产生循环 |

### 🟢 LOW（可接受或容易修复）

| # | 风险项 | 影响 |
|---|--------|------|
| L1 | `app/pages/trends.py` 包含分页计算 | 薄层业务逻辑，可快速抽离到 Query Handler |
| L2 | 数据库无外键约束 | 利于微服务拆分，但单体内部缺乏参照完整性保护 |

---

## 3. 技术债列表（按修复成本排序）

| ID | 债务项 | 当前成本 | 未来利息 | 偿还建议 |
|----|--------|----------|----------|----------|
| TD-1 | `app.py` → `wsgi.py` 重命名 | 1 小时 | 每次新人 onboarding 踩坑 2 小时 | 重命名 + 更新入口脚本 |
| TD-2 | `TransactionManager` 接入 SQLAlchemy `session.begin()` | 4 小时 | 每次生产数据不一致修复 8+ 小时 | 重写 `atomic()` 为真实 session 事务管理器 |
| TD-3 | `generator.py` / `model_router.py` 迁移到 `llm.adapter` + `LLMGateway` | 16 小时 | 每新增一个 provider 重复 workaround 4 小时 | 将 `CopywriterGenerator` 委托给 `LLMGateway.chat()` |
| TD-4 | `MemoryBank` / `TrendDatabase` / `EditorWorkflow` 移除内存 SOT | 24 小时 | 水平扩展时必须完全重写 | 以 PostgreSQL 为唯一 SOT；JSON 仅作冷备份 |
| TD-5 | Repository 返回 Plain Domain Entity（非 ORM 对象） | 12 小时 | 领域逻辑与 DB schema 耦合，schema 迁移成本递增 | 引入 `TrendEntity` / `MemoryEntryEntity` dataclass；Repository 做 ORM→Entity 映射 |
| TD-6 | `GenerationService` 拆分为 `GenerationService` + `AsyncTaskService` + `BatchOrchestrationService` | 16 小时 | 每次修改 generation 逻辑需理解 560 行上下文 | 按职责拆分，通过接口协作 |
| TD-7 | `domains/editor/application` 移除对 `services` 的依赖 | 4 小时 | 微服务拆分时必须重构接口 | DTO 移至 `domains/editor/application/dto.py` |
| TD-8 | Celery batch task 添加 Outbox / Saga 模式 | 8 小时 | 孤儿 job 记录堆积，需人工清理 | 引入 `Outbox` 表：先写 outbox，再发 Celery task，Worker 消费后删 outbox |
| TD-9 | `TrendScheduler` 从 threading 迁移到 Celery Beat | 8 小时 | 多 Worker 时每个进程启动独立爬虫线程 | 将 `_do_crawl` 包装为 Celery periodic task |
| TD-10 | `ModelRouter` 健康状态迁移到 Redis | 4 小时 | 负载均衡失效，故障 provider 仍被路由 | 使用 Redis 计数器 + TTL 实现跨进程健康共享 |

---

## 4. 后续演进建议

### 阶段一：止血（1-2 周）—— 解决 CRITICAL

1. **重命名 `app.py` → `wsgi.py`（已完成）**，消除模块/包名冲突。
2. **修复 `TransactionManager.atomic()`**：接入 `SQLAlchemy session.begin()`，补偿失败不再静默吞异常，而是记录 error log 并抛 `CompensationFailedError`。
3. **将 `llm.adapter` 接入生产代码**：
   - 创建 `LLMGateway` 实例并注册到 DI Container。
   - 修改 `services/generation_service.py` 的 `_do_generate()`，使其通过 `LLMGateway.chat()` 调用，而非直接实例化 `CopywriterGenerator`/`ModelRouter`。
   - 保留 `model_router.py` 作为兼容层（deprecated），但内部委托给 `LLMGateway`。

### 阶段二：治理（3-4 周）—— 解决 HIGH

4. **Repository ORM 隔离**：
   - 在 `domains/*/domain/entity.py` 中定义纯 dataclass Entity。
   - Repository 实现层做 `ORM Model → Entity` 映射后返回。
   - `GenerationService` 停止直接 `session.query()`，全部通过 Repository 接口。
5. **移除进程内内存状态**：
   - `MemoryBank`：以 PostgreSQL `pgvector` 为向量存储，移除 `LightVectorSearch`（或降级为纯 DB 查询的缓存）。
   - `TrendDatabase`：移除 JSON cache SOT，PostgreSQL 为唯一真相源；JSON 文件仅作为离线备份。
   - `EditorWorkflow`：将 `index.json` 迁移到 PostgreSQL 表；文件系统仅存储 markdown 内容。
6. **Service 拆分**：
   - 从 `GenerationService` 中提取 `AsyncTaskService`（Celery 任务提交/查询/取消）。
   - 从 `GenerationService` 中提取 `BatchOrchestrationService`（parent-child job 管理）。

### 阶段三：扩展（5-8 周）—— 水平扩展 + 微服务就绪

7. **状态外迁**：
   - `ModelRouter` 健康状态 → Redis 共享计数器。
   - `PromptBuilder._composer` 注册表 → PostgreSQL `prompt_registry` 表 + Redis 缓存。
   - `TrendScheduler` → Celery Beat periodic task，状态存 Redis。
8. **引入 Outbox 模式**：
   - 在 `generate_batch_task` 中：先写 `outbox` 表（同一 DB 事务），再异步消费 outbox 发送 Celery group。
   - 消除孤儿 job 记录。
9. **跨服务调用抽象**：
   - 为 `EditorService → GenerationService` 的同步调用引入 `IGenerationServiceClient` 接口。
   - 当前实现为 in-process adapter；未来可替换为 HTTP/gRPC client 而不改 `EditorService`。
10. **数据库外键补全**：
    - `GenerationJob.parent_batch_id` 添加 FK + `ON DELETE CASCADE`。
    - 或明确决定走"无 FK 的微服务友好路线"，并在应用层实现级联删除逻辑。

---

## 5. 是否适合进入生产环境

### 结论：**有条件通过（Conditional Go）**

| 场景 |  verdict | 前提条件 |
|------|----------|----------|
| **内部工具 / 单实例 / 低并发 (< 10 QPS)** | ✅ **可以投产** | C1 已修复 (`app.py` → `wsgi.py`) |
| **多 Worker Celery / 中等并发 (10-100 QPS)** | ⚠️ **需完成阶段一 + 阶段二** | 必须修复 TD-2, TD-3, TD-4, TD-6 |
| **面向外部用户 / 高并发 (> 100 QPS)** | ❌ **不可投产** | 必须完成全部三个阶段 |
| **未来计划拆分为微服务** | ❌ **当前架构不支持** | 必须完成全部三个阶段 + 引入服务间通信基础设施 |

### 投产检查清单（Minimum Viable Production）

- [x] `app.py` 已重命名为 `wsgi.py`，入口脚本已更新
- [ ] `TransactionManager.atomic()` 已接入真实 DB 事务
- [ ] `llm.adapter` 已接入 `GenerationService`，旧 `ModelRouter` 已标记 deprecated
- [ ] `MemoryBank` / `TrendDatabase` / `EditorWorkflow` 的进程内状态已迁移到 PostgreSQL
- [ ] Celery batch task 已添加 outbox 或至少添加孤儿 job 清理任务
- [ ] 已配置 Redis 作为 `ModelRouter` 健康状态的共享存储（或单 Worker 部署）
- [ ] 已配置 PostgreSQL 连接池（`pool_size`, `max_overflow`）
- [ ] 已配置 Celery `acks_late=True` + 任务幂等性验证

---

## 6. 一句话总结

> **新架构（`llm/`, `domains/`, `TokenAccounting`, `OpenTelemetry Tracing`）设计精良，但与生产代码（`vcw_copywriter/`, `services/`）之间存在严重的"架构断层"；当前系统是一艘底部仍在漏水的旧船，但上层已经搭好了漂亮的甲板。建议先止血（修复事务、接入 adapter、消除进程内状态），再谈微服务拆分。**
