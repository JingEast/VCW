# Generation Domain — 文案生成子域

## 业务边界
负责将用户输入（主题、受众、政策要点等）转换为高质量文案的完整生命周期，包括：
- 提示词组装（Prompt Composition）
- LLM 生成调用（单次 / 流式 / 批量）
- 质量检查（Quality Check）
- 结果持久化（文件 + 草稿索引）
- 异步任务调度

## 三层职责

### application/
- `GenerateCopyUseCase` — 单次生成用例编排
- `GenerateBatchUseCase` — 批量生成用例编排
- `SubmitAsyncUseCase` — 异步任务提交编排
- `GenerationCommand`, `GenerationResult` — DTO

### domain/
- `Copy` — 文案实体（内容、元信息、质量评分）
- `Topic`, `Audience` — 值对象
- `Prompt` — 值对象（system + user）
- `QualityChecker` — 领域服务（质量规则判断）
- `IGenerationRepository` — 仓库接口
- `CopyGenerated` — 领域事件

### infrastructure/
- `GenerationRepository` — 仓库实现（JSON 文件 + ORM）
- `LlmClient` — LLM API 客户端（OpenAI / ModelRouter 适配）
- `FileStore` — 生成的 markdown 文件存储
- `TaskQueueAdapter` — 异步任务队列适配器
