# 测试体系建设

## 测试金字塔

```
     ┌─────────┐
     │   E2E   │  ← Playwright (5%)
     ├─────────┤
     │  API    │  ← pytest + TestClient (25%)
     ├─────────┤
     │  Unit   │  ← pytest + mock (70%)
     └─────────┘
```

## 测试分类

### 1. 单元测试 (Unit Test)

| 目标 | 工具 | 覆盖率目标 |
|------|------|------------|
| 业务逻辑 | pytest | 80%+ |
| 工具函数 | pytest | 90%+ |
| 模型验证 | pytest | 85%+ |

### 2. 集成测试 (Integration Test)

| 目标 | 工具 | 覆盖率目标 |
|------|------|------------|
| DB Repository | pytest + 内存 SQLite | 75%+ |
| Celery 任务 | pytest + 内存 broker | 60%+ |
| 配置加载 | pytest | 90%+ |

### 3. API 测试 (API Test)

| 目标 | 工具 | 覆盖率目标 |
|------|------|------------|
| 所有 API 端点 | pytest + Flask TestClient | 100% |
| 认证流程 | pytest + JWT | 100% |
| 错误响应 | pytest | 100% |

### 4. 安全测试 (Security Test)

| 目标 | 工具 |
|------|------|
| SQL 注入 | pytest + sqlmap |
| XSS | pytest + XSS 载荷 |
| CSRF | pytest + 伪造请求 |
| 认证绕过 | pytest + 令牌篡改 |

### 5. 冒烟测试 (Smoke Test)

| 目标 | 工具 |
|------|------|
| 服务启动 | Shell + curl |
| 健康检查 | curl /health |
| 依赖连接 | Python 脚本 |

## 覆盖率目标

| 模块 | 目标 | 当前估计 |
|------|------|----------|
| app/core | 85% | 60% |
| app/api | 90% | 40% |
| app/pages | 70% | 30% |
| vcw_copywriter | 80% | 50% |
| **总计** | **≥ 80%** | **~45%** |

## CI 集成

```yaml
# .github/workflows/ci.yml 补充
- name: Run tests with coverage
  run: pytest tests/ --cov=. --cov-report=xml --cov-fail-under=80
```
