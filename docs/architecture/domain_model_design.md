# Domain Model Design — VCW DDD-lite

> 生成日期：2026-05-31
> 范围：`domains/*/domain/` 四层边界上下文核心业务模型

---

## 一、总体设计原则

1. **纯 Python**：domain 层不依赖 Flask、SQLAlchemy、HTTP、第三方 SDK。
2. **Entity 有标识**：通过 `id` 区分，支持生命周期和行为方法。
3. **Value Object 不可变**：`frozen=True` dataclass，基于值比较。
4. **Domain Service 无状态**：纯业务逻辑，不持有实体状态。
5. **业务规则显性化**：校验在 `__post_init__` 和行为方法中，失败即抛 `ValueError`。

---

## 二、Entity 关系图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Generation Domain                                 │
│                                                                              │
│   ┌─────────────┐         ┌─────────────────┐                               │
│   │   Copy      │◄────────│  GenerationTask │                               │
│   │  (entity)   │  1..*   │    (entity)     │                               │
│   └─────────────┘         └─────────────────┘                               │
│          │                            │                                      │
│          │ has                        │ has                                  │
│          ▼                            ▼                                      │
│   ┌─────────────┐              ┌──────────────┐                             │
│   │QualityReport│              │GenerationParams│                            │
│   │ (value obj) │              │  (value obj)  │                             │
│   └─────────────┘              └──────────────┘                             │
│                                                                              │
│   Domain Service: QualityChecker                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              Editor Domain                                   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │                          Draft (entity)                         │       │
│   │  id: DraftId │ topic │ original_content │ edited_content │ status│      │
│   │  edit_history: List[EditRecord] │ created_at │ updated_at         │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│          │                                                                   │
│          │ has                                                               │
│          ▼                                                                   │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                      │
│   │  DraftId    │   │ DraftStatus │   │ EditRecord  │                      │
│   │ (value obj) │   │  (enum VO)  │   │ (value obj) │                      │
│   └─────────────┘   └─────────────┘   └─────────────┘                      │
│                                                                              │
│   Domain Service: DiffEngine, DeAIOptimizer                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              Prompt Domain                                   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │                    PromptTemplate (entity)                      │       │
│   │  name │ system_template │ version │ created_at │ updated_at     │       │
│   │  render(**kwargs) → system_prompt                               │       │
│   │  extract_placeholders() → List[str]                             │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│          │                                                                   │
│          │ rendered by                                                       │
│          ▼                                                                   │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │                    RenderedPrompt (value obj)                   │       │
│   │  system: str │ user: str                                        │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                                                                              │
│   Domain Service: PromptComposer, TemplateValidator                          │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              Trend Domain                                    │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │                          Trend (entity)                         │       │
│   │  id │ title │ summary │ url │ published_at │ heat │ category    │       │
│   │  tags │ is_selected │ selected_at │ is_archived                  │       │
│   │  select() │ archive() │ is_fresh │ is_expired │ is_stale         │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│          │                                                                   │
│          │ scored by                                                         │
│          ▼                                                                   │
│   ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐          │
│   │  TimelinessScore│   │    Category     │   │   TrendFilter   │          │
│   │   (value obj)   │   │   (value obj)   │   │   (value obj)   │          │
│   └─────────────────┘   └─────────────────┘   └─────────────────┘          │
│                                                                              │
│   Domain Service: TrendScorer, TrendClassifier, TrendFilterEngine            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、Entity 详述

### 3.1 Generation Domain

#### `Copy`
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | UUID 唯一标识 |
| `topic` | `str` | 文案主题 |
| `content` | `str` | 生成的正文 |
| `meta` | `str` | 模型、耗时等元信息 |
| `quality_report` | `QualityReport` | 质量检查报告 |
| `created_at` | `datetime` | 创建时间 |

**行为方法**：
- `is_passed(strict_mode: bool) -> bool` — 根据质量报告判断是否通过
- `update_content(new_content: str) -> None` — 精修更新

**不变量**：
- `id` 不能为空
- `topic` 不能为空

#### `GenerationTask`
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 任务唯一标识 |
| `params` | `GenerationParams` | 生成参数 |
| `status` | `str` | pending / running / completed / failed |
| `result` | `List[Copy]` | 生成的文案列表 |
| `error_message` | `str` | 失败信息 |
| `created_at` | `datetime` | 创建时间 |
| `completed_at` | `datetime` | 完成时间 |

**行为方法**：
- `mark_running()` / `mark_completed(copies)` / `mark_failed(message)`

---

### 3.2 Editor Domain

#### `Draft`
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `DraftId` | 草稿唯一标识（时间戳格式） |
| `topic` | `str` | 主题 |
| `original_content` | `str` | 原始文案 |
| `edited_content` | `str` | 精修后的文案 |
| `status` | `DraftStatus` | draft / edited / final |
| `source_filepath` | `str` | 来源文件路径 |
| `meta` | `str` | 元信息 |
| `edit_history` | `List[EditRecord]` | 编辑历史 |
| `created_at` | `datetime` | 创建时间 |
| `updated_at` | `datetime` | 更新时间 |

**行为方法**：
- `edit(new_content, note)` — 记录编辑历史，状态变更为 EDITED
- `finalize()` — 定稿，状态变更为 FINAL
- `revert_to_original()` — 回退到原始内容
- `get_diff()` — 返回 (original, edited)

**不变量**：
- `topic` 不能为空
- `original_content` 不能为空

---

### 3.3 Prompt Domain

#### `PromptTemplate`
| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 模板名称（唯一标识） |
| `system_template` | `str` | 模板字符串（含占位符） |
| `version` | `str` | 版本号 |
| `created_at` | `datetime` | 创建时间 |
| `updated_at` | `datetime` | 更新时间 |

**行为方法**：
- `render(**kwargs) -> str` — 替换占位符生成最终 system prompt
- `update_template(new_template)` — 更新模板内容
- `extract_placeholders() -> List[str]` — 提取所有 `{var}` 变量名
- `is_valid -> bool` — 检查是否包含必要占位符

**不变量**：
- `name` 不能为空
- `system_template` 不能为空

---

### 3.4 Trend Domain

#### `Trend`
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `TrendId` | 唯一标识 |
| `title` | `str` | 标题（必填） |
| `summary` | `str` | 摘要 |
| `url` | `str` | 来源链接 |
| `published_at` | `str` | 发布时间（ISO） |
| `heat` | `int` | 热度（0-100） |
| `category` | `Category` | 分类 |
| `tags` | `List[str]` | 标签 |
| `is_selected` | `bool` | 是否已选用 |
| `selected_at` | `str` | 选用时间 |
| `is_archived` | `bool` | 是否已归档 |

**行为方法**：
- `select()` — 标记为已选用
- `archive()` / `unarchive()` — 归档/取消归档
- `update_heat(new_heat)` — 更新热度（0-100）
- `add_tag(tag)` / `remove_tag(tag)` — 标签管理

**派生属性**：
- `is_fresh` — 7 天内发布
- `is_expired` — 超过 365 天
- `is_stale` — 超过 90 天

**不变量**：
- `title` 不能为空
- `heat` 必须在 0-100 之间

---

## 四、Value Object 详述

### 4.1 Generation Domain

| Value Object | 字段 | 业务含义 |
|-------------|------|---------|
| `Topic` | `value: str` | 文案主题，不可为空 |
| `Audience` | `value: str` | 目标受众，默认"港宝家长" |
| `Prompt` | `system: str, user: str` | 完整的 system + user prompt |
| `QualityIssue` | `category, level, message, suggestion` | 单条质量问题（level ∈ {error, warning, info}） |
| `QualityReport` | `issues: List[QualityIssue]` | 质量检查报告集合，支持 `is_passed(strict_mode)` |
| `GenerationParams` | `topic, audience, core_data, ...` | 生成所需的全部输入参数 |

### 4.2 Editor Domain

| Value Object | 字段 | 业务含义 |
|-------------|------|---------|
| `DraftId` | `value: str` | 草稿唯一标识（时间戳） |
| `DraftStatus` | Enum: `DRAFT`, `EDITED`, `FINAL` | 草稿生命周期状态 |
| `EditRecord` | `timestamp, note, before_length, after_length` | 单次编辑的不可变记录 |
| `DeAIPrompt` | `template: str` | 去 AI 味优化指令模板，支持 `render(content)` |

### 4.3 Prompt Domain

| Value Object | 字段 | 业务含义 |
|-------------|------|---------|
| `PromptContext` | `topic, audience, core_data, ...` | 组装 prompt 所需的全部上下文参数 |
| `PromptSection` | `name: str, content: str` | Prompt 段落 |
| `RenderedPrompt` | `system: str, user: str` | 渲染后的最终 prompt，含长度属性 |
| `SampleCopy` | `name: str, content: str` | 参考样本文案 |

### 4.4 Trend Domain

| Value Object | 字段 | 业务含义 |
|-------------|------|---------|
| `TrendId` | `value: str` | 热点唯一标识 |
| `Category` | `value: str` | 分类（DSE/升学/政策/插班/留学/联考/其他） |
| `TimelinessScore` | `value: float` | 时效性评分（0-100），支持 `is_hot(threshold)` |
| `HeatLevel` | `value: int` | 热度等级（0-100），映射为 🔥爆/🔥热/🔥温/🧊凉/🧊冷 |
| `TrendFilter` | `time_filter, sort_by, category_filter, limit, offset` | 查询过滤器 |
| `TrendReport` | `total_count, category_distribution, ...` | 统计报告 |

---

## 五、Domain Service 详述

### 5.1 Generation Domain

#### `QualityChecker`
- **职责**：对文案内容进行自动化质量检查
- **方法**：`check(content, strict_mode) -> QualityReport`
- **检查项**：
  1. 结构（五段式）
  2. 数据时效性（禁止模糊年份、旧年份、疫情表述）
  3. 禁用词（学术化连接词）
  4. AI 味（结构化连接词、书面化表达）
  5. 长度（200-2000 字范围提示）
  6. 行动号召（CTA 检测）
  7. 元信息泄露（"AI生成"等词汇）

### 5.2 Editor Domain

#### `DiffEngine`
- **职责**：计算两段文本的差异统计
- **方法**：
  - `compute_diff(original, edited) -> (added, removed, unchanged)`
  - `has_changes(original, edited) -> bool`

#### `DeAIOptimizer`
- **职责**：构建去 AI 味优化的提示词
- **方法**：`build_prompt(content) -> str`
- **说明**：实际的 LLM 调用由应用层委托 Generation Domain 完成

### 5.3 Prompt Domain

#### `PromptComposer`
- **职责**：根据模板和上下文组装完整的 system + user prompt
- **方法**：`compose(template, context) -> RenderedPrompt`

#### `TemplateValidator`
- **职责**：验证 PromptTemplate 的完整性
- **方法**：`validate(template) -> List[str]`（错误列表，空列表表示通过）
- **必填占位符**：`memory_section`, `knowledge_section`

### 5.4 Trend Domain

#### `TrendScorer`
- **职责**：计算热点的时效性评分和综合评分
- **方法**：
  - `calc_timeliness_score(trend) -> TimelinessScore`
    - 24h 内：100 分
    - 7 天内：线性衰减到 70
    - 30 天内：衰减到 40
    - 90 天内：衰减到 10
    - 90 天以上：接近 0
  - `calc_composite_score(trend) -> float` = 时效性 × 0.5 + 热度 × 0.5

#### `TrendClassifier`
- **职责**：根据标题和摘要推断分类
- **方法**：`classify(title, summary) -> Category`
- **关键词映射**：DSE → "DSE/考评局/放榜"；升学 → "JUPAS/录取/联招"；等等

#### `TrendFilterEngine`
- **职责**：对 Trend 列表应用过滤器并排序分页
- **方法**：`apply(trends, filter) -> List[Trend]`
- **排序方式**：composite（综合评分）/ time（时间）/ heat（热度）

---

## 六、与现有代码的映射

| 现有代码 | Domain 模型 | 说明 |
|---------|------------|------|
| `vcw_copywriter/checker.py` | `QualityChecker` | 质量检查逻辑完整迁移 |
| `vcw_copywriter/editor.py` 的 draft dict | `Draft` Entity | dict → 强类型 Entity |
| `vcw_copywriter/prompt_builder.py` | `PromptComposer` + `PromptTemplate` | 模板组装逻辑 |
| `vcw_copywriter/trend_db.py` 的 trend dict | `Trend` Entity | dict → 强类型 Entity |
| `vcw_copywriter/trend_db.py` 的评分 | `TrendScorer` | 时效性算法提取 |

---

## 七、质量门禁

| 工具 | 结果 |
|------|------|
| **pytest** | 42 passed |
| **ruff** | All checks passed |
| **mypy** | 0 errors (29 source files) |

---

*设计结束。下一步（DDD-lite 第三步）建议：为每个 domain 建立 `application/` 层的 UseCase 和 DTO，将 `services/*_service.py` 中的编排逻辑逐步迁移过来。*
