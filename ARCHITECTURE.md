# VCW 项目架构框架

> **项目**：港籍升学热点文案批量生成器（VCW - Viral CopyWriter）
> **技术栈**：Python 3.12 + Flask + SQLAlchemy 2.0 + OpenAI API + Playwright

---

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Web 层 (Presentation)                           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  index.html │ │ trends.html │ │ batch.html  │ │ editor.html │ ...       │
│  │  (文案生成)  │ │  (热点发现)  │ │ (批量生成)  │ │  (精修编辑)  │           │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘           │
│         │               │               │               │                   │
│         └───────────────┴───────┬───────┴───────────────┘                   │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Flask Application Factory                        │   │
│  │   create_app() → init_services() → register_blueprints()            │   │
│  │   ┌─────┐ ┌──────┐ ┌─────┐ ┌──────┐ ┌─────┐ ┌──────┐ ┌─────┐      │   │
│  │   │main │ │trends│ │batch│ │editor│ │memory│ │config│ │ ... │      │   │
│  │   └─────┘ └──────┘ └─────┘ └──────┘ └─────┘ └──────┘ └─────┘      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            服务层 (Service Layer)                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │ app_services    │  │ prompt_service  │  │    scheduler    │             │
│  │ (全局单例初始化) │  │ (Prompt构建服务) │  │  (定时爬取调度)  │             │
│  └────────┬────────┘  └─────────────────┘  └─────────────────┘             │
│           │                                                                 │
│  ┌────────▼────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   Config        │  │  MemoryBank     │  │  TrendDatabase  │             │
│  │  (配置管理)      │  │   (记忆库)       │  │   (热点数据库)   │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          核心引擎层 (Core Engine)                            │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  PromptBuilder  │  │  AutoPrompt     │  │ ViralAnalyzer   │             │
│  │  (提示词构建)    │  │ (自动参数推断)   │  │  (爆款规律分析)  │             │
│  │  ├─ Registry    │  │  ├─ SceneConfig │  │                 │             │
│  │  ├─ Composer    │  │  └─ Trend→Param │  │                 │             │
│  │  └─ Loader      │  │                 │  │                 │             │
│  └────────┬────────┘  └─────────────────┘  └─────────────────┘             │
│           │                                                                 │
│  ┌────────▼────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │    Generator    │  │ BatchGenerator  │  │  ModelRouter    │             │
│  │  (LLM API调用)  │  │  (批量多角度)   │  │ (多模型路由)    │             │
│  │  ├─ generate()  │  │  ├─ 焦虑型      │  │  ├─ 优先级切换  │             │
│  │  ├─ stream()    │  │  ├─ 数据型      │  │  ├─ 健康检查    │             │
│  │  └─ save()      │  │  └─ 故事型      │  │  └─ 自动降级    │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  TrendScraper   │  │   EditorWorkflow│  │ QualityChecker  │             │
│  │  (热点爬虫Facade)│  │   (精修工作流)   │  │  (质量检查)     │             │
│  │  ├─ RSS Provider│  │  ├─ save_draft()│  │  ├─ 时效性      │             │
│  │  ├─ HTML Prov.  │  │  ├─ de_ai()     │  │  ├─ 去AI味      │             │
│  │  ├─ GoogleNews  │  │  └─ finalize()  │  │  └─ 结构检查    │             │
│  │  ├─ BaiduHot    │  │                 │  │                 │             │
│  │  └─ Wechat      │  │                 │  │                 │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Scraping Pipeline (Filter → Dedupe → Normalize)                   │   │
│  │  教育相关性过滤 → URL/标题去重 → 时效评分排序                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            数据层 (Data Layer)                               │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SQLAlchemy ORM + Repository                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │   │
│  │  │   Trend     │  │ MemoryEntry │  │GenerationJob│               │   │
│  │  │  (热点表)    │  │  (记忆表)   │  │  (任务表)   │               │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘               │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  GenerationResult (生成结果表)                               │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                     │   │
│  │  SQLite (默认)  ←─── 环境变量 DATABASE_URL ───→  PostgreSQL       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         文件系统                                     │   │
│  │  data/generated/*.md    data/edited/*.md    data/*.json (备份)      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 目录结构

```
VCW/
├── app/                              # Flask Web 应用层
│   ├── __init__.py                   # Application Factory (create_app)
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/                   # 10 个 Blueprint
│   │       ├── main.py               # 首页、文案生成、SSE流式、异步任务
│   │       ├── trends.py             # 热点发现、爬取、调度器
│   │       ├── batch.py              # 批量生成（多角度变体）
│   │       ├── editor.py             # 精修编辑器、去AI味API
│   │       ├── memory.py             # 记忆库管理
│   │       ├── prompts.py            # Prompt编辑与预览
│   │       ├── config.py             # LLM配置、多模型端点
│   │       ├── history.py            # 生成历史文件列表
│   │       ├── resources.py          # 业务资源库（网站/关键词/流程）
│   │       └── api_misc.py           # 杂项API（保存流、模型状态、预览）
│   ├── core/
│   │   ├── __init__.py
│   │   └── extensions.py             # 扩展注册点（预留）
│   └── services/
│       ├── __init__.py
│       ├── app_services.py           # 全局单例初始化层
│       └── prompt_service.py         # Prompt构建服务（复用逻辑）
│
├── vcw_copywriter/                   # 核心引擎包
│   ├── __init__.py
│   ├── config.py                     # 配置管理 (Config类 + DEFAULT_CONFIG)
│   ├── prompt_builder.py             # 提示词构建（Registry适配层）
│   ├── auto_prompt.py                # 自动参数推断（场景识别）
│   ├── generator.py                  # LLM API调用（OpenAI兼容）
│   ├── batch_generator.py            # 批量多角度生成
│   ├── model_router.py               # 多模型智能路由与负载均衡
│   ├── trend_scraper.py              # 热点爬虫 Facade (兼容入口)
│   ├── trend_db.py                   # 热点数据库（Adapter→Repository）
│   ├── memory.py                     # 记忆库（Adapter→Repository）
│   ├── task_queue.py                 # 异步任务队列（Adapter→Repository）
│   ├── editor.py                     # 精修工作流（草稿/去AI味/定稿）
│   ├── checker.py                    # 质量检查器（时效/结构/去AI味）
│   ├── scheduler.py                  # 定时爬取调度器
│   ├── viral_analyzer.py             # 爆款规律分析器
│   ├── knowledge_base.py             # 业务知识库（网站/关键词/流程）
│   ├── light_vector_search.py        # 轻量向量搜索（预留）
│   ├── main.py                       # CLI入口（旧）
│   │
│   ├── prompts/                      # 【新】Prompt Registry + Versioning
│   │   ├── __init__.py
│   │   ├── schemas.py                # PromptVersion / PromptMetadata / PromptSpec
│   │   ├── registry.py               # PromptRegistry（注册/查询/依赖解析）
│   │   ├── loader.py                 # PromptLoader（Markdown+Frontmatter）
│   │   ├── composer.py               # PromptComposer（legacy/modular组合）
│   │   ├── defaults.py               # 默认Prompt集合（19个PromptSpec）
│   │   └── templates/                # 可扩展模板目录
│   │       ├── system/
│   │       ├── scenes/
│   │       ├── styles/
│   │       ├── samples/
│   │       └── sections/
│   │
│   ├── scraper/                      # 【重构】Provider + Pipeline 架构
│   │   ├── __init__.py               # TrendScraper Facade
│   │   ├── base.py                   # HttpClient
│   │   ├── pipelines.py              # Filter / Dedupe / Normalize
│   │   ├── config.py                 # 爬虫配置（源列表/关键词）
│   │   ├── utils.py                  # 工具函数（时间解析/相似度）
│   │   └── providers/
│   │       ├── rss_provider.py       # RSS源爬取
│   │       ├── html_provider.py      # HTML新闻源爬取
│   │       ├── google_news_provider.py
│   │       ├── baidu_hot_provider.py
│   │       └── playwright_provider.py # 搜狗微信（Playwright）
│   │
│   └── db/                           # 【新】SQLAlchemy ORM + Repository
│       ├── __init__.py
│       ├── session.py                # Engine / Session / init_db
│       ├── models.py                 # 4个ORM实体
│       └── repositories/
│           ├── __init__.py
│           ├── base.py               # BaseRepository (Generic[T])
│           ├── trend_repository.py
│           ├── memory_repository.py
│           ├── job_repository.py
│           └── result_repository.py
│
├── templates/                        # Jinja2 模板
│   ├── base.html                     # 基础布局（导航栏/Flash/页脚）
│   ├── index.html                    # 文案生成主页面
│   ├── trends.html                   # 热点发现页面
│   ├── batch.html                    # 批量生成页面
│   ├── editor.html                   # 精修编辑器
│   ├── memory.html                   # 记忆库管理
│   ├── prompts.html                  # Prompt编辑
│   ├── config.html                   # 配置管理
│   ├── history.html                  # 历史文案
│   ├── resources.html                # 业务资源库
│   └── result.html                   # 生成结果展示
│
├── static/                           # 静态资源
│   ├── css/style.css                 # 全局样式（1280行）
│   ├── js/                           # （空，JS全部内联在模板中）
│   └── logo.jpg
│
├── data/                             # 数据存储
│   ├── vcw.db                        # 主SQLite数据库（SQLAlchemy）
│   ├── task_queue.db                 # 任务队列降级SQLite
│   ├── trend_db.json                 # 热点JSON备份（自动迁移源）
│   ├── memory_db.json                # 记忆JSON备份（自动迁移源）
│   ├── trend_cache.json              # 热点爬取缓存
│   ├── prompts_custom.json           # 自定义Prompt
│   ├── scheduler.json                # 调度器状态
│   ├── viral_patterns.json           # 爆款规律缓存
│   ├── generated/                    # 生成的文案 .md
│   └── edited/                       # 精修后的文案 .md
│
├── config.json                       # 应用配置文件
├── requirements.txt                  # Python依赖
├── run.py                            # 启动脚本
└── ARCHITECTURE.md                   # 本文档
```

---

## 3. 各层详细设计

### 3.1 Web 层 — Flask Application Factory + Blueprint

**设计目标**：将原 `wsgi.py` 单文件（1069行）拆分为模块化架构，同时保持所有模板中 `url_for()` 和 `request.endpoint` 的兼容性。

**关键机制**：
- **Application Factory**：`create_app()` 控制初始化顺序（服务 → Blueprint → 兼容性Patch）
- **裸 Endpoint 别名**：`_register_naked_endpoints()` 为每个 Blueprint view 注册裸名别名（如 `main.index` → `index`），使 `url_for('index')` 无需修改即可工作
- **Request.endpoint Patch**：自定义 `_CompatRequest` 覆盖 `endpoint` property，返回裸名（如 `index` 而非 `main.index`），使模板中 `request.endpoint == 'index'` 的判断继续生效

**10 个 Blueprint**：

| Blueprint | 前缀 | 核心功能 |
|---|---|---|
| `main` | `/` | 首页、文案生成（同步/SSE流式/异步）、结果展示 |
| `trends` | `/trends` | 热点列表、爬取、选用、手动录入、定时调度器控制 |
| `batch` | `/batch` | 批量生成（焦虑型/数据型/故事型多角度） |
| `editor` | `/editor` | 精修编辑、保存、去AI味优化 |
| `memory` | `/memory` | 记忆条目CRUD、规避标记 |
| `prompts` | `/prompts` | System Prompt可视化编辑、预览 |
| `config` | `/config` | LLM配置、多模型端点管理 |
| `history` | `/history` | 生成历史文件浏览 |
| `resources` | `/resources` | 业务资源库（网站/关键词/服务流程） |
| `api_misc` | `/api` | 杂项API端点 |

---

### 3.2 服务层 — 全局单例初始化

`app/services/app_services.py` 在 `create_app()` 的早期被调用，初始化所有全局单例：

```python
# 初始化顺序
ensure_dirs()           # 创建 data/ 等目录
config = Config()       # 加载 config.json，支持环境变量覆盖
memory_bank = MemoryBank()   # 记忆库（Adapter→Repository）
trend_db = TrendDatabase()   # 热点数据库（Adapter→Repository）
editor = EditorWorkflow()    # 精修工作流
scheduler = get_scheduler()  # 定时爬取调度器（后台线程）
viral_analyzer = ViralAnalyzer()  # 爆款分析器预热
```

**环境变量覆盖**：
- `VCW_API_KEY` → `config.llm.api_key`
- `VCW_BASE_URL` → `config.llm.base_url`
- `VCW_MODEL` → `config.llm.model`

---

### 3.3 核心引擎层

#### 3.3.1 Prompt 系统（Registry + Versioning）

**架构演进**：原 `prompt_builder.py` 中的 `SYSTEM_PROMPT_TEMPLATE`（270行大字符串）+ `SAMPLE_COPYWRITING`（5个样本）被重构为 **Prompt Registry + Versioning** 系统。

**核心组件**：

| 组件 | 职责 |
|---|---|
| `PromptSpec` | 单个Prompt规格：id / type / version / content / metadata / dependencies |
| `PromptVersion` | 语义化版本号（major.minor.patch），支持比较排序 |
| `PromptMetadata` | 元信息：author / description / tags / compatible_scenes / extra |
| `PromptRegistry` | 内存注册表：register / get(按版本) / list_by_type / resolve_dependencies |
| `PromptLoader` | 从文件系统加载：支持 Markdown+YAML Frontmatter / JSON / YAML |
| `PromptComposer` | 动态组合：legacy模式（输出不变）/ modular模式（拆分段落组装） |

**两种组合模式**：
- **legacy（默认）**：使用完整的 `system:copywriting@1.0.0` 和 `user:copywriting@1.0.0` 模板，通过 `str.format()` 注入变量，输出与重构前 **字节级一致**
- **modular**：从 section / scene / style 片段动态组装，支持未来细粒度定制

**向后兼容**：`prompt_builder.py` 和 `auto_prompt.py` 的公共接口签名 100% 保持不变，内部委托给 `PromptComposer`。

#### 3.3.2 文案生成管线

```
用户输入（主题/受众/数据/政策/场景）
    │
    ▼
┌─────────────────┐
│  AutoPromptBuilder │ ← 业务场景权重计分识别（5大场景）
│  ├─ _infer_scene() │   强信号+3 / 中信号+2 / 弱信号+1 / 排斥信号-5
│  └─ build_from_trend()│  热点 → 自动填充参数
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  PromptComposer │ ← 组合 System Prompt + User Prompt
│  ├─ compose_system() │  注入 memory_section + knowledge_section + viral_text
│  └─ compose_user()   │  注入变量 + 参考样本 + 场景限定
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ CopywriterGenerator│ or │  ModelRouter    │ ← 多模型端点智能路由
│ (单模型模式)      │     │  ├─ 优先级排序   │
│  ├─ generate()   │     │  ├─ 健康检查     │
│  ├─ generate_stream()│  │  ├─ 自动降级     │
│  └─ save_generated()│  │  └─ 流式输出     │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│ QualityChecker  │ ← 8项自动化质检
│  ├─ 结构检查     │   （五段式、CTA）
│  ├─ 时效性检查   │   （禁止模糊年份、疫情表述）
│  ├─ 禁用词检查   │   （学术连接词）
│  ├─ 去AI味检查   │   （机械排比、复杂从句）
│  ├─ 字数检查     │   （600-900字）
│  ├─ 学校名称检查 │   （≥3个具体学校）
│  └─ 元信息泄露检查│   （禁止"AI生成"等）
└────────┬────────┘
         │
         ▼
    生成结果 → data/generated/*.md
         │
         ▼
┌─────────────────┐
│ EditorWorkflow  │ ← 精修工作流
│  ├─ save_draft() │   保存原始文案为草稿
│  ├─ update_edited()│ 人工精修 / 一键去AI味
│  └─ finalize()   │   标记为最终版本
└─────────────────┘
```

**批量生成**：`BatchGenerator` 支持一次生成 3 个角度变体（焦虑型 / 数据型 / 故事型），串行调用避免限流。

#### 3.3.3 热点爬虫 — Provider + Pipeline 架构

**架构演进**：原 `trend_scraper.py` 中 2192 行的 God Object 被拆分为 **5 Provider + 3 Pipeline**。

**Provider 层**（每个独立实现 `fetch()`）：

| Provider | 数据源 | 技术 | 状态 |
|---|---|---|---|
| `RssProvider` | 明报 / 南华早报 / RTHK / 政府新闻处 RSS | `feedparser` + `requests` | ⚠️ 部分RSS 403 |
| `HtmlProvider` | 学为教育 / 唯寻 / 新通等教育网站 | `requests` + `BeautifulSoup` | ✅ 正常 |
| `GoogleNewsProvider` | Google News API | `requests` + JSON | ✅ 正常 |
| `BaiduHotProvider` | 百度热搜榜 | `requests` + HTML解析 | ❌ 页面结构变化，失效 |
| `SogouWechatProvider` | 搜狗微信搜索 | `Playwright` + stealth | ❌ 服务端反爬，不可突破 |

**Pipeline 层**（链式处理）：

```python
all_trends → NormalizePipeline() → DedupePipeline() → FilterPipeline() → 最终结果
```

| Pipeline | 职责 |
|---|---|
| `NormalizePipeline` | 补充发布时间 → 计算时效评分 → 按综合得分排序 |
| `DedupePipeline` | URL去重 → 标题相似度去重（阈值0.85） |
| `FilterPipeline` | 教育关键词过滤 → 过期数据过滤（365天） |

**Facade**：`TrendScraper.fetch_all()` 接口完全不变，内部 ThreadPoolExecutor 并行调度 6 个数据源。

---

### 3.4 数据层 — SQLAlchemy ORM + Repository Pattern

**架构演进**：原 JSON 文件存储被重构为 **ORM + Repository 层**，默认 SQLite，可通过 `DATABASE_URL` 环境变量切换 PostgreSQL。

**适配器模式（Adapter Pattern）**：旧模块（`TrendDatabase` / `MemoryBank` / `TaskQueue`）保留原对外接口，内部调用 Repository。数据库为空时自动从 JSON 迁移。

#### 3.4.1 实体模型

```python
Trend           → 表 trends          # 热点数据（原 trend_db.json）
MemoryEntry     → 表 memory_entries  # 记忆条目（原 memory_db.json）
GenerationJob   → 表 generation_jobs # 异步任务（原 task_queue.db）
GenerationResult → 表 generation_results # 生成结果（原 data/generated/*.md）
```

#### 3.4.2 Repository 层

| Repository | 实体 | 核心能力 |
|---|---|---|
| `TrendRepository` | `Trend` | 批量导入、多维度查询（时间/分类/排序）、推荐算法、自动归档 |
| `MemoryRepository` | `MemoryEntry` | 按主题/标签查询、规避标记、报告生成 |
| `JobRepository` | `GenerationJob` | 任务提交、状态更新、取消、启动恢复、清理 |
| `ResultRepository` | `GenerationResult` | 结果保存、按主题查询 |

#### 3.4.3 自动迁移策略

```
应用启动
    │
    ▼
TrendDatabase.__init__()
    │
    ├── init_db() → 创建SQLAlchemy表
    │
    ├── TrendRepository.get_all() → 检查DB是否有数据
    │       ├── 有数据 → 直接使用
    │       └── 无数据 → 读取 data/trend_db.json
    │                     └── Trend.from_dict() → 批量导入DB
    │
    └── 后续 _save() → 增量同步DB + 双写JSON备份
```

**双写策略**：每次 `_save()` 同时写入数据库（主）和 JSON 文件（备份），JSON 作为降级预案。

#### 3.4.4 数据库配置

| 后端 | 配置方式 | 用途 |
|---|---|---|
| SQLite | 默认 `sqlite:///data/vcw.db` | 开发/测试/单机部署 |
| PostgreSQL | 环境变量 `DATABASE_URL` | 生产部署 |

连接池：`pool_pre_ping=True`, `pool_recycle=3600`

---

## 4. 数据流

### 4.1 文案生成完整数据流

```
┌─────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ 用户表单 │────→│  main.index  │────→│ build_full_prompts() │────→│ LLM API     │
│ ( topic )│     │  (GET /)     │     │  1. memory_text      │     │ (generate)  │
└─────────┘     └─────────────┘     │  2. knowledge_text   │     └──────┬──────┘
                                     │  3. system_prompt    │            │
                                     │  4. user_prompt      │            ▼
                                     └─────────────┘     ┌─────────────┐
                                                          │ QualityChecker│
                                                          │ (check_and_report)
                                                          └──────┬──────┘
                                                                 ▼
                                                          ┌─────────────┐
                                                          │ EditorWorkflow│
                                                          │ (save_draft)  │
                                                          └──────┬──────┘
                                                                 ▼
                                                          ┌─────────────┐
                                                          │ data/generated/│
                                                          │   *.md       │
                                                          └─────────────┘
```

### 4.2 热点发现数据流

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ TrendScheduler  │────→│ TrendScraper    │────→│  TrendDatabase  │
│ (定时/手动触发)  │     │ ├─ 6 Provider并行│     │ (import_from_scraper)
│                 │     │ ├─ 3 Pipeline处理│     │                 │
│                 │     │ └─ 缓存到JSON   │     │                 │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                          │
                                                          ▼
                                                   ┌─────────────┐
                                                   │  SQLAlchemy  │
                                                   │  (trends表)  │
                                                   └─────────────┘
```

### 4.3 记忆反馈闭环

```
生成文案 ──→ 质量检查发现问题 ──→ 人工录入记忆库 ──→ 下次生成自动注入
    │                              (memory.html)      (memory_section)
    │                                                   ▲
    └────────────────── 精修优化后 ──────────────────────┘
                    (editor.html → 标记规避)
```

---

## 5. 关键设计模式

| 模式 | 应用场景 | 文件 |
|---|---|---|
| **Application Factory** | Flask 应用创建与配置解耦 | `app/__init__.py` |
| **Blueprint** | 路由模块化，10个独立业务模块 | `app/api/routes/*.py` |
| **Facade** | `TrendScraper` 对外隐藏 Provider+Pipeline 复杂度 | `vcw_copywriter/scraper/__init__.py` |
| **Adapter** | `TrendDatabase`/`MemoryBank`/`TaskQueue` 保留旧接口，内部调用 Repository | `vcw_copywriter/trend_db.py`, `memory.py`, `task_queue.py` |
| **Repository** | 数据库访问抽象，支持 SQLite/PostgreSQL 切换 | `vcw_copywriter/db/repositories/*.py` |
| **Registry** | Prompt 版本化管理，支持多版本共存和动态组合 | `vcw_copywriter/prompts/registry.py` |
| **Strategy** | `PromptComposer` 支持 legacy/modular 两种组合策略 | `vcw_copywriter/prompts/composer.py` |
| **Singleton** | 全局服务单例（Config / MemoryBank / TrendDatabase / Scheduler） | `app/services/app_services.py` |
| **Pipeline** | 热点数据处理链：Normalize → Dedupe → Filter | `vcw_copywriter/scraper/pipelines.py` |
| **Observer** | SSE 流式输出（EventSource）和异步任务状态轮询 | `app/api/routes/main.py` |

---

## 6. 依赖关系图

```
Flask Web 层
├── main ──→ prompt_service ──→ prompt_builder ──→ prompts (Registry)
│              └── generator, model_router, task_queue, checker
├── trends ──→ trend_db, scheduler, auto_prompt ──→ scraper (Provider+Pipeline)
├── batch ──→ prompt_builder, batch_generator ──→ generator
├── editor ──→ editor, generator
├── memory ──→ memory_bank
├── prompts ──→ prompt_builder, knowledge_base
├── config ──→ config
├── history ──→ config
├── resources ──→ knowledge_base
└── api_misc ──→ editor, model_router, prompt_service

核心引擎
├── prompt_builder ──→ memory, knowledge_base, prompts (Registry)
├── auto_prompt ──→ viral_analyzer
├── generator ──→ openai
├── model_router ──→ openai
├── batch_generator ──→ generator, checker
├── trend_scraper ──→ scraper (Provider+Pipeline)
├── trend_db ──→ db.repositories.trend_repository
├── memory ──→ db.repositories.memory_repository
├── task_queue ──→ db.repositories.job_repository (PG) / sqlite (fallback)
├── editor ──→ generator (de_ai)
├── checker ──→ (纯文本分析)
├── scheduler ──→ trend_scraper, trend_db
├── viral_analyzer ──→ (纯文本分析)
└── knowledge_base ──→ (静态数据)

数据层
├── db.session ──→ sqlalchemy
├── db.models ──→ sqlalchemy
└── db.repositories.* ──→ db.session, db.models
```

---

## 7. 配置说明

### 7.1 config.json

```json
{
  "llm": {
    "provider": "openai",
    "api_key": "",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o",
    "temperature": 0.7,
    "max_tokens": 2000,
    "endpoints": []           // 多模型端点配置（可选）
  },
  "memory": {
    "db_path": "data/memory_db.json",
    "max_entries_per_topic": 10
  },
  "output": {
    "save_dir": "data/generated",
    "auto_save": true
  },
  "quality_check": {
    "enabled": true,
    "strict_mode": false
  }
}
```

### 7.2 环境变量

| 变量 | 作用 | 优先级 |
|---|---|---|
| `VCW_API_KEY` | 覆盖 `config.json` 中的 LLM API Key | 最高 |
| `VCW_BASE_URL` | 覆盖 LLM Base URL | 最高 |
| `VCW_MODEL` | 覆盖 LLM Model | 最高 |
| `DATABASE_URL` | 切换数据库后端（如 `postgresql://...`） | 最高 |

---

## 8. 扩展点

### 8.1 添加新的数据源 Provider

1. 在 `vcw_copywriter/scraper/providers/` 下新建 `xxx_provider.py`
2. 继承 `HttpClient` 或实现 `fetch()` 方法
3. 在 `TrendScraper.__init__()` 中注册

### 8.2 添加新的业务场景

1. 在 `AutoPromptBuilder.SCENE_CONFIG` 中添加场景配置
2. 在 `vcw_copywriter/prompts/templates/scenes/` 下新建场景模板 `.md` 文件
3. 可选：在 `SAMPLE_COPYWRITING` 中添加对应样本文案

### 8.3 自定义 Prompt 模板

1. 在 `vcw_copywriter/prompts/templates/` 下新建 `.md` 文件（带 YAML Frontmatter）
2. 调用 `prompt_builder.reload_prompts()` 热加载
3. 或使用 `PromptComposer(mode="modular")` 动态组合

### 8.4 添加新的 Repository

1. 在 `vcw_copywriter/db/models.py` 中定义新的 ORM 实体
2. 在 `vcw_copywriter/db/repositories/` 下新建 Repository 类，继承 `BaseRepository[T]`
3. 在 `vcw_copywriter/db/session.py` 的 `init_db()` 中自动建表

### 8.5 添加新的 LLM Endpoint

在 Web 界面 `/config` 的"多模型端点配置"中动态添加，无需重启。

---

## 9. 技术债务与已知问题

| 问题 | 位置 | 影响 | 状态 |
|---|---|---|---|
| 百度热搜页面结构变化 | `baidu_hot_provider.py` | 无法获取百度热搜数据 | ❌ 不可修复（反爬） |
| 搜狗微信服务端反爬 | `playwright_provider.py` | 微信文章无法抓取 | ❌ 不可突破 |
| RTHK/政府新闻处被过滤 | `FilterPipeline` | 教育过滤后全部排除 | ⚠️ 综合新闻源非教育专用 |
| `static/js/` 为空 | 前端 | 所有 JS 内联在模板中，维护困难 | ⚠️ 建议提取 |
| MemoryRepository JSON过滤 | `memory_repository.py` | 全量加载后Python端过滤 | ⚠️ PostgreSQL JSONB可优化 |
| TaskQueue 降级逻辑 | `task_queue.py` | PG失败时回退独立SQLite，数据不统一 | ⚠️ 建议统一 |
