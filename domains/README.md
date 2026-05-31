# Domains — DDD-lite 目录结构

> 本目录为 VCW 项目预留的 DDD-lite 边界化上下文（Bounded Context）根目录。
> 当前阶段**仅建立目录结构**，不迁移任何业务逻辑。

---

## 设计原则

1. **仅建立结构** — 当前不迁移 `services/` 和 `vcw_copywriter/` 中的任何代码。
2. **按领域划分** — 每个子目录对应一个业务子域（Generation / Editor / Prompt / Trend）。
3. **分层清晰** — 每个领域内部分为 `application` / `domain` / `infrastructure` 三层。
4. **渐进迁移** — 未来重构时，按领域逐步将 `services/*_service.py` 和 `vcw_copywriter/*` 迁移至此。

---

## 目录总览

```
domains/
├── generation/          # 文案生成子域
│   ├── application/     # 应用服务、用例编排、DTO
│   ├── domain/          # 实体、值对象、领域服务、领域事件
│   └── infrastructure/  # 仓储实现、外部 API 客户端、ORM 映射
├── editor/              # 精修编辑器子域
│   ├── application/
│   ├── domain/
│   └── infrastructure/
├── prompt/              # Prompt 工程子域
│   ├── application/
│   ├── domain/
│   └── infrastructure/
└── trend/               # 热点发现子域
    ├── application/
    ├── domain/
    └── infrastructure/
```

---

## 三层职责说明

### application/
- **应用服务（Application Service）**：编排领域对象完成用例，如 `GenerateCopyUseCase`
- **DTO / Command / Query**：定义输入输出数据结构
- **事务边界**：声明式事务（`@transactional`）或 Unit of Work
- **无业务规则**：不包含 if/else 业务判断，只做流程串联

### domain/
- **实体（Entity）**：有唯一标识的领域对象，如 `Draft`, `Copy`
- **值对象（Value Object）**：无标识的不可变对象，如 `Topic`, `Angle`
- **领域服务（Domain Service）**：跨实体的纯业务逻辑，如 `QualityChecker`
- **领域事件（Domain Event）**：记录领域状态变更，如 `CopyGenerated`
- **仓库接口（Repository Interface）**：`ICopyRepository`, `IDraftRepository`
- **纯 Python**：不依赖 Flask、SQLAlchemy、文件系统、HTTP 等基础设施

### infrastructure/
- **仓库实现（Repository Implementation）**：实现 domain 中定义的仓库接口
- **外部服务客户端**：LLM API 客户端、RSS 爬虫适配器
- **ORM / 持久化映射**：SQLAlchemy Model、JSON 文件读写、缓存适配器
- **消息队列适配器**：TaskQueue 封装、事件发布器
- **配置读取**：将 `config.json` / 环境变量映射为领域配置对象

---

## 与现有代码的映射关系（未来迁移方向）

| 现有代码 | 未来迁移目标 |
|---------|------------|
| `services/generation_service.py` | `domains/generation/application/` |
| `services/editor_service.py` | `domains/editor/application/` |
| `services/prompt_service.py` | `domains/prompt/application/` |
| `services/scheduler_service.py` + `services/history_service.py` | `domains/trend/application/` |
| `vcw_copywriter/generator.py`, `checker.py` | `domains/generation/domain/` |
| `vcw_copywriter/editor.py` | `domains/editor/domain/` |
| `vcw_copywriter/prompt_builder.py` | `domains/prompt/domain/` |
| `vcw_copywriter/trend_db.py`, `scraper/` | `domains/trend/infrastructure/` |
| `vcw_copywriter/task_queue.py` | 各 domain 的 `infrastructure/` |

---

## 迁移原则

1. **先内后外** — 先把 `domain/` 层的纯业务逻辑写清楚，再写 `infrastructure/` 的适配器，最后写 `application/` 的编排。
2. **仓库优先** — 定义 `I*Repository` 接口，让 `services/` 通过接口调用，再逐步实现 `infrastructure/` 的仓库。
3. **避免大爆炸重构** — 一次只迁移一个领域（如先 `generation`，再 `editor`）。
4. **保持测试通过** — 每次迁移后运行 `pytest tests/`，确保行为不变。
