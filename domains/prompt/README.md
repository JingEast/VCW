# Prompt Domain — Prompt 工程子域

## 业务边界
负责提示词模板的管理、组装与预览：
- System Prompt 模板存储与热更新
- User Prompt 动态组装（主题 + 受众 + 政策 + 记忆 + 知识库）
- Prompt 预览与调试
- 自定义模板持久化

## 三层职责

### application/
- `BuildPromptUseCase` — 构建完整 prompts
- `PreviewPromptUseCase` — 预览渲染效果
- `SaveTemplateUseCase` — 保存自定义模板
- `PromptCommand`, `PromptPreviewDTO` — DTO

### domain/
- `PromptTemplate` — 实体（system 模板字符串、版本）
- `PromptContext` — 值对象（topic, audience, memory, knowledge ...）
- `PromptComposer` — 领域服务（模板 + 上下文 → 最终 prompt）
- `IPromptRepository` — 仓库接口
- `TemplateUpdated` — 领域事件

### infrastructure/
- `PromptRepository` — 仓库实现（JSON 文件 `prompts_custom.json`）
- `TemplateLoader` — 模板加载器（Registry + 文件系统）
- `KnowledgeBaseAdapter` — 知识库读取适配器
- `MemoryBankAdapter` — 记忆库读取适配器
