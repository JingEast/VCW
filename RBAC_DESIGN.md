# RBAC 权限体系设计

## 角色定义

| 角色 | 标识 | 说明 |
|------|------|------|
| SuperAdmin | superadmin | 系统超级管理员，拥有所有权限 |
| Admin | admin | 业务管理员，管理内容和用户 |
| Operator | operator | 运营人员，可生成和编辑文案 |
| Auditor | auditor | 审计人员，只读访问日志和数据 |
| User | user | 普通用户，仅使用基础功能 |

## 权限模型

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    User     │────▶│  UserRole   │◀────│    Role     │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                     ┌─────────────┐
                     │  Permission │
                     └─────────────┘
```

## 权限矩阵

| 权限 | SuperAdmin | Admin | Operator | Auditor | User |
|------|:----------:|:-----:|:--------:|:-------:|:----:|
| 用户管理 | ✅ | ✅ | ❌ | ❌ | ❌ |
| 角色分配 | ✅ | ✅ | ❌ | ❌ | ❌ |
| Prompt 管理 | ✅ | ✅ | ❌ | ❌ | ❌ |
| 趋势抓取触发 | ✅ | ✅ | ✅ | ❌ | ❌ |
| 文案生成 | ✅ | ✅ | ✅ | ❌ | ✅ |
| 文案编辑 | ✅ | ✅ | ✅ | ❌ | ✅ |
| 记忆库管理 | ✅ | ✅ | ✅ | ❌ | ❌ |
| 配置修改 | ✅ | ✅ | ❌ | ❌ | ❌ |
| 查看日志 | ✅ | ✅ | ❌ | ✅ | ❌ |
| 查看报表 | ✅ | ✅ | ✅ | ✅ | ❌ |
| 查看趋势 | ✅ | ✅ | ✅ | ✅ | ✅ |

## API 权限映射

| API 端点 | 所需角色 |
|----------|----------|
| POST /api/v1/generate/* | user+ |
| POST /api/v1/editor/de-ai | user+ |
| POST /api/v1/prompts | admin+ |
| POST /api/v1/trends/scheduler/toggle | admin+ |
| POST /api/v1/trends/scheduler/trigger | operator+ |
| GET /api/v1/trends/scheduler/status | operator+ |
| GET /metrics | auditor+ |
| GET /debug/profile | admin+ |

## 页面权限映射

| 页面 | 所需角色 |
|------|----------|
| / | public |
| /generate | user+ |
| /batch | user+ |
| /editor | user+ |
| /memory | operator+ |
| /prompts | admin+ |
| /config | admin+ |
| /history | user+ |
| /resources | user+ |
| /trends | operator+ |
