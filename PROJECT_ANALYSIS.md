# PROJECT_ANALYSIS.md — VCW 深度分析

## 1. 项目概览

- **项目名称**: 港籍升学热点文案批量生成器 (VCW)
- **技术栈**: Python 3.12 + Flask 3.x + SQLAlchemy 2.x + Celery + Redis
- **业务领域**: 教育内容生成 / 港籍升学资讯
- **架构模式**: Blueprint + Application Factory + Dependency Injection
- **当前阶段**: PO-06 已完成（CI/CD + 部署自动化）

## 2. 技术架构

- **Web 框架**: Flask 3.x（Application Factory 模式）
- **ORM**: SQLAlchemy 2.0 + Alembic 迁移治理
- **数据库**: SQLite（开发）/ PostgreSQL（生产，支持 pgvector）
- **缓存**: Flask-Caching + Redis
- **任务队列**: Celery + Redis
- **LLM 集成**: OpenAI 兼容接口（OpenAI / DeepSeek / Kimi）
- **容器化**: Docker + docker-compose（staging / prod 多环境）
- **CI/CD**: GitHub Actions（lint → test → migration-check → docker-smoke → push）
- **监控**: Prometheus + Grafana + 结构化日志 + TraceId

## 3. 文件结构

```
VCW/
├── app/                    # Flask 应用核心
│   ├── api/v1/             # REST API Blueprints (18 路由)
│   ├── pages/              # 页面 Blueprints (22 路由)
│   ├── core/               # 配置、日志、限流、缓存、监控
│   └── __init__.py         # Application Factory
├── vcw_copywriter/         # 业务逻辑层
│   ├── db/                 # ORM 模型 + Repository + 迁移
│   ├── prompts/            # Prompt 模板
│   └── scraper/            # 数据采集
├── templates/              # Jinja2 模板 (11)
├── static/                 # CSS/JS/图片 (15)
├── alembic/                # 迁移脚本 (5 个版本)
├── .github/workflows/      # CI/CD (ci/cd/release)
├── scripts/                # 部署/回滚/健康检查
├── tests/                  # 测试套件 (517 passed)
└── docs/                   # 运维文档
```

## 4. 数据库结构

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| trends | 热点数据 | category, published_at, embedding(Vector) |
| memory_entries | 迭代记忆 | topic, is_avoided, created_at |
| generation_jobs | 生成任务 | status, celery_task_id, parent_batch_id |
| prompt_versions | Prompt 版本 | version, content, is_active |
| generation_results | 生成结果 | content, quality_score |

- **索引**: 已添加性能索引（is_archived, category, published_at, status 等）
- **迁移**: 线性历史，单 head，零漂移

## 5. API 结构

- **API 路由**: 18 个（/generate/*, /editor/*, /prompts/*, /trends/*, /misc/*）
- **页面路由**: 22 个（/, /batch, /editor, /memory, /prompts, /config, /history, /resources, /trends）
- **功能覆盖**: 文案生成、批量处理、编辑器、记忆库、Prompt 管理、趋势抓取、配置管理

## 6. 安全分析

| 检查项 | 状态 | 说明 |
|--------|------|------|
| SECRET_KEY | ⚠️ 警告 | 未设置时随机生成，生产环境需配置 |
| DEBUG | ✅ | .env.example 中 FLASK_DEBUG=false |
| SQL 注入 | ✅ 低风险 | 使用 SQLAlchemy ORM + 参数化查询 |
| XSS | ⚠️ 中等 | 使用 Jinja2 模板自动转义，需检查用户输入 |
| CSRF | ⚠️ 中等 | 未配置 Flask-WTF CSRF 保护 |
| 硬编码密码 | ✅ 无 | 敏感信息通过环境变量/配置文件管理 |
| .env 泄露 | ✅ 无 | .gitignore 已排除 .env |
| 限流 | ✅ | Flask-Limiter 已配置 |

**安全评分**: 75/100

## 7. 风险分析

| 风险 | 等级 | 说明 |
|------|------|------|
| 日志文件锁定 | 中 | Windows 下日志轮转 PermissionError (WinError 32) |
| SECRET_KEY 未设置 | 中 | 生产环境必须配置 |
| VCW_API_KEY 未设置 | 高 | LLM 生成将失败 |
| SQLite 生产使用 | 中 | 建议切换到 PostgreSQL |
| Celery/Redis 未运行 | 中 | 异步任务依赖外部服务 |

## 8. 开发路线图

### 下一阶段（PO-07 候选）

1. **用户认证系统** — 登录/注册/权限管理（当前无鉴权）
2. **API 文档** — Swagger/OpenAPI 自动生成
3. **前端优化** — React/Vue SPA 替代 Jinja2 模板
4. **测试覆盖提升** — 目标 80%+ 覆盖率
5. **性能监控** — APM 集成（Datadog/New Relic）
6. **多租户支持** — 隔离不同用户数据
7. **LLM 模型管理** — 支持更多模型切换与 Fallback

### 技术债务

- 补充 CSRF 保护
- 统一错误处理格式
- 补充 API 鉴权中间件
- Windows 日志权限修复

## 9. 部署方案

- **Staging**: docker-compose.staging.yml（FLASK_DEBUG=true, 单副本）
- **Production**: docker-compose.prod.yml（FLASK_DEBUG=false, 多副本, PostgreSQL）
- **CI/CD**: GitHub Actions 自动构建 → Docker Hub → 自动部署 Staging
- **Rollback**: scripts/rollback.sh 支持一键回滚

## 10. 后续建议

- 配置 GitHub Secrets（DOCKER_USERNAME, DOCKER_PASSWORD）
- 创建 staging / production Environments
- 配置分支保护规则
- 配置 PostgreSQL 生产数据库
- 配置 Redis 和 Celery Worker
- 完成首次 Release v0.0.1 验证
