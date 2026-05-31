# Editor Domain — 精修编辑器子域

## 业务边界
负责草稿（Draft）的完整生命周期管理，以及 AI 辅助优化：
- 草稿创建、读取、更新、定稿
- 原始版 vs 精修版差异对比
- 编辑历史追踪
- AI 去 AI 味优化（De-AI Optimization）

## 三层职责

### application/
- `SaveDraftUseCase` — 保存草稿
- `UpdateDraftUseCase` — 更新精修内容 + 定稿
- `OptimizeWithAIUseCase` — AI 辅助优化编排
- `DraftCommand`, `DraftDTO`, `DiffDTO` — DTO

### domain/
- `Draft` — 草稿实体（id, topic, original, edited, status, history）
- `EditRecord` — 值对象（编辑记录）
- `DraftStatus` — 枚举（draft / edited / final）
- `DiffEngine` — 领域服务（文本差异计算）
- `IDraftRepository` — 仓库接口
- `DraftFinalized` — 领域事件

### infrastructure/
- `DraftRepository` — 仓库实现（JSON index + markdown 文件）
- `EditorStorage` — 文件系统适配（编辑目录管理）
- `LlmOptimizationClient` — 委托 `Generation Domain` 的 LLM 客户端进行优化
