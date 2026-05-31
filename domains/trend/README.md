# Trend Domain — 热点发现子域

## 业务边界
负责教育热点数据的采集、存储、筛选与手动录入：
- 多源 RSS / 新闻爬虫调度
- 热点时效性评分与去重
- 热点分类与标签
- 手动录入与归档
- 首页数据看板（生成历史统计）

## 三层职责

### application/
- `FetchTrendsUseCase` — 手动触发爬取
- `SelectTrendUseCase` — 选用热点并推断文案参数
- `ListTrendsUseCase` — 分页查询热点
- `GetDashboardStatsUseCase` — 首页数据看板统计
- `TrendCommand`, `TrendDTO` — DTO

### domain/
- `Trend` — 实体（id, title, summary, url, heat, timeliness, category）
- `TimelinessScore` — 值对象（时效性评分）
- `Category` — 枚举（DSE / 升学 / 政策 ...）
- `TrendScorer` — 领域服务（时效性算法、去重逻辑）
- `ITrendRepository` — 仓库接口
- `TrendImported` — 领域事件

### infrastructure/
- `TrendRepository` — 仓库实现（JSON + ORM 混合）
- `ScraperAdapter` — 爬虫适配器（TrendScraper 封装）
- `SchedulerAdapter` — 调度器适配器（定时爬取触发）
- `HistoryStore` — 生成历史文件扫描适配器（`data/generated/*.md`）
