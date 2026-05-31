# VCW Service Layer 最终审查报告

> 生成日期：2026-05-31
> 审查范围：`app/`（Routes + Core） + `services/`（Service Layer）

---

## 一、最终目录结构

```
VCW/
├── services/                           # 业务编排层（统一入口）
│   ├── __init__.py
│   ├── base/
│   │   ├── __init__.py
│   │   ├── base_service.py             # 抽象基类：权限、事务、日志
│   │   ├── permission_manager.py       # 统一权限管理
│   │   └── transaction_manager.py      # 统一事务管理（含补偿机制）
│   ├── generation_service.py           # 文案生成服务
│   ├── editor_service.py               # 精修编辑器服务
│   ├── prompt_service.py               # Prompt 构建与模板管理服务
│   ├── scheduler_service.py            # 热点调度与趋势管理服务
│   └── history_service.py              # 生成历史与数据看板服务
│
├── app/                                # HTTP 层（仅请求/响应转换）
│   ├── __init__.py                     # Flask App Factory
│   ├── api/v1/                         # API Blueprints（JSON）
│   │   ├── common.py
│   │   ├── editor.py
│   │   ├── generate.py
│   │   ├── misc.py
│   │   ├── prompts.py
│   │   └── trends.py
│   ├── core/                           # 基础设施
│   │   ├── container.py                # DI 容器（dependency-injector）
│   │   └── logging_config.py           # 日志配置
│   ├── pages/                          # 页面 Blueprints（HTML）
│   │   ├── batch.py
│   │   ├── config.py
│   │   ├── editor.py
│   │   ├── history.py
│   │   ├── main.py
│   │   ├── memory.py
│   │   ├── prompts.py
│   │   ├── resources.py
│   │   └── trends.py
│   └── services/                       # 包标记（已清理）
│       └── __init__.py
│
├── vcw_copywriter/                     # 纯 AI 能力层（无 HTTP 逻辑）
│   ├── prompt_builder.py
│   ├── generator.py
│   ├── model_router.py
│   ├── checker.py
│   ├── batch_generator.py
│   ├── editor.py
│   ├── memory.py
│   ├── trend_db.py
│   ├── scheduler.py
│   ├── task_queue.py
│   ├── viral_analyzer.py
│   ├── auto_prompt.py
│   ├── main.py                         # CLI 入口（仅 run.py 使用）
│   ├── scraper/
│   ├── prompts/
│   └── db/
│
├── tests/                              # 测试套件
├── bandit.yaml                         # 安全扫描配置
└── pyproject.toml                      # mypy / bandit 配置
```

---

## 二、最终调用链

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           HTTP 层（Routes）                                │
│  app/pages/*  +  app/api/v1/*                                           │
│  ─────────────────────────────────────────                               │
│  职责：参数提取 → 调用 Service → 模板渲染 / JSON 响应                       │
│  禁止：直接调用 vcw_copywriter、直接文件 I/O、直接 ORM 访问                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ get_service("xxx")
┌─────────────────────────────────────────────────────────────────────────┐
│                         Service 层（业务编排）                              │
│  services/*                                                             │
│  ─────────────────────────────────────────                               │
│  GenerationService    ──→ 文案生成、流式、批量、异步任务                      │
│  EditorService        ──→ 草稿生命周期、AI 优化                              │
│  PromptService        ──→ Prompt 构建、预览、模板持久化                      │
│  SchedulerService     ──→ 热点爬取、调度器生命周期、趋势查询                  │
│  HistoryService       ──→ 生成历史、数据看板统计                             │
│  ─────────────────────────────────────────                               │
│  统一：继承 BaseService（权限 + 事务 + 日志）                                │
│  统一：专属 Error 类（GenerationError / EditorError / ...）                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ 注入 core 实例
┌─────────────────────────────────────────────────────────────────────────┐
│                          Core 层（纯能力）                                  │
│  vcw_copywriter/*                                                       │
│  ─────────────────────────────────────────                               │
│  prompt_builder, generator, model_router, checker, batch_generator       │
│  editor, memory, trend_db, scheduler, task_queue                        │
│  scraper, prompts, db                                                   │
│  ─────────────────────────────────────────                               │
│  职责：纯 AI 能力、数据持久化、外部爬取                                     │
│  禁止：Flask / HTTP / 业务编排 / 直接面向用户的校验                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 调用示例

```
GET /trends
    → pages_trends.trends_page()
        → get_service("scheduler_service")
        → scheduler_service.list_trends(page, per_page, ...)
            → trend_db.get_all(...)
                → JSON 文件索引 / ORM 查询

POST /api/v1/generate/async
    → api_v1_generate.generate_async()
        → get_service("generation_service")
        → generation_service.submit_async_generate(req_data)
            → task_queue.submit("generate", worker_fn)
                → worker_fn → generation_service.generate_copy()
                    → prompt_builder.build_full_prompts()
                    → CopywriterGenerator.generate()
                    → checker.check_and_report()
```

---

## 三、删除文件列表

| # | 文件 | 删除原因 |
|---|------|---------|
| 1 | `app/container.py` | 废弃的自定义 DI 容器；全项目已迁移至 `app/core/container.py` |
| 2 | `app/services/app_services.py` | 废弃的服务注册逻辑；无人引用 |
| 3 | `app/services/prompt_service.py` | 旧 helper 函数；逻辑已迁移至 `services/prompt_service.py` |
| 4 | `app/api/routes/__init__.py` | 空文件；无人引用 |
| 5 | `app/core/extensions.py` | 空占位符；无人引用 |
| 6 | `vcw_copywriter/db/repositories/result_repository.py` | `ResultRepository` 全项目零引用 |

---

## 四、本次重构改动汇总

### 4.1 新增基础设施

| 文件 | 说明 |
|------|------|
| `services/base/base_service.py` | Service 抽象基类：统一权限检查、事务上下文、补偿操作、结构化日志 |
| `services/base/permission_manager.py` | 统一权限管理器（当前：API Key 白名单） |
| `services/base/transaction_manager.py` | 统一事务管理器（数据库事务 + 文件补偿机制） |
| `bandit.yaml` | bandit 安全扫描配置 |

### 4.2 Service 层实现/重写

| 文件 | 动作 | 说明 |
|------|------|------|
| `services/generation_service.py` | 重写 | 继承 BaseService；移除分散的 `_check_api_key`；统一使用 `_require_permission` + `_transaction` |
| `services/editor_service.py` | 重写 | 继承 BaseService；新增 DTO；`optimize_with_ai` 统一 raise `EditorError` |
| `services/prompt_service.py` | 从空壳实现 | 承接所有 Prompt 构建、预览、模板持久化、资源上下文、模型状态查询 |
| `services/scheduler_service.py` | 从空壳实现 | 承接所有热点爬取、调度器生命周期、趋势查询与维护 |
| `services/history_service.py` | 新增 | 承接生成历史文件扫描、数据看板统计 |

### 4.3 Routes 层瘦身

| 文件 | 改动 |
|------|------|
| `app/api/v1/misc.py` | 修复 broken import + tuple unpacking bug；移除 `ModelRouter` 直接实例化；委托 `PromptService` / `EditorService` |
| `app/api/v1/prompts.py` | 移除所有 `vcw_copywriter` 直接导入；全部委托 `PromptService` |
| `app/api/v1/trends.py` | 移除 `flash()`（API 不应使用 session flash）；全部委托 `SchedulerService` |
| `app/api/v1/editor.py` | 简化 `optimize_with_ai` 响应处理（不再检查 `result.success`） |
| `app/pages/prompts.py` | 移除 `vcw_copywriter.prompt_builder` 直接访问；委托 `PromptService.get_template_context()` |
| `app/pages/resources.py` | 移除 `vcw_copywriter.knowledge_base` 直接访问；委托 `PromptService.get_resources_context()` |
| `app/pages/trends.py` | 移除 `TrendScraper` / `auto_fill_from_trend` 直接调用；全部委托 `SchedulerService` |
| `app/pages/history.py` | 移除文件系统 I/O；委托 `HistoryService.list_recent_files()` |
| `app/pages/main.py` | 移除文件系统 I/O（recent_files + stats）；委托 `HistoryService` |
| `app/pages/memory.py` | 为 `memory_delete` 添加异常保护 |
| `app/pages/config.py` | 为 `float()` / `int()` 转换添加异常保护 |

### 4.4 DI 容器更新

| 文件 | 改动 |
|------|------|
| `app/core/container.py` | 新增 `transaction_manager`、`permission_manager`、`prompt_service`、`scheduler_service`、`history_service` provider |

---

## 五、技术债列表

以下问题在本次重构中**识别但未修复**，留作后续迭代：

| # | 位置 | 问题 | 优先级 |
|---|------|------|--------|
| 1 | `vcw_copywriter/main.py` | 完整的 CLI 应用（含 `input()`/`print()` 菜单）混在 core 库中；应移至 `cli/` 包 | Low |
| 2 | `vcw_copywriter/generator.py` | `save_generated()` 包含文件 I/O；持久化应移至 Service/Repository | Low |
| 3 | `vcw_copywriter/editor.py` | `_save_markdown()` / `_save_index()` 耦合文件 I/O 与编辑逻辑 | Low |
| 4 | `vcw_copywriter/memory.py` | JSON 文件 + SQLAlchemy ORM 双持久化混合；应统一为单一存储 | Low |
| 5 | `vcw_copywriter/trend_db.py` | 同上，JSON + ORM 双持久化；且包含重复的时间性评分算法 | Low |
| 6 | `vcw_copywriter/scheduler.py` | `_do_crawl()` 包含业务管道逻辑（应移至 Service）；JSON 状态持久化耦合 | Low |
| 7 | `vcw_copywriter/db/models.py` | `PromptVersion` ORM 类有 Alembic 迁移表，但零代码引用 | Low |
| 8 | `vcw_copywriter/scraper/providers/baidu_hot_provider.py` | 已失效（注释标注），仍注册在 provider 列表中 | Low |
| 9 | `app/pages/memory.py:61-69` | `memory_delete` 直接修改 `memory_bank.data["entries"]` 并调用私有 `_save()`；待 `MemoryBank.delete_entry()` 实现后替换 | Low |
| 10 | `vcw_copywriter/db/models.py` | `datetime.utcnow()` 弃用警告（Python 3.12+） | Low |
| 11 | `wsgi.py` 文件名 | 原 `app.py` 已重命名，消除与 `app/` 包命名冲突 | Fixed |

---

## 六、质量门禁结果

| 工具 | 结果 |
|------|------|
| **pytest** | 42 passed |
| **ruff** | All checks passed |
| **mypy** | Success: no issues found in 33 source files |
| **bandit** | 0 issues (Low: 0, Medium: 0, High: 0) |

---

## 七、架构守则（最终版）

1. **Routes 层三不原则**
   - 不直接调用 `vcw_copywriter.*`
   - 不直接访问 ORM / 数据库
   - 不包含业务逻辑（仅参数提取 + 响应转换）

2. **Service 层三统一**
   - 统一继承 `BaseService`
   - 统一异常（每个 Service 定义专属 `*Error`）
   - 统一日志（`self.logger = logging.getLogger(__class__.__name__)`）

3. **Core 层两禁止**
   - 禁止导入 Flask / 处理 HTTP
   - 禁止包含面向用户的校验或业务编排

---

*报告结束。*
