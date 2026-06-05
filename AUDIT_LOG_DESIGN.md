# 审计日志系统设计

## 目标

记录所有关键操作，满足安全审计与合规要求。

## 日志分类

| 类型 | 表名 | 记录内容 |
|------|------|----------|
| 登录日志 | audit_login | 登录/登出/失败 |
| API 访问日志 | audit_api | 所有 API 请求 |
| 权限变更日志 | audit_permission | 角色分配/权限修改 |
| 数据变更日志 | audit_data | 增删改操作 |
| 安全事件日志 | audit_security | 异常/攻击/违规 |

## 统一字段结构

```python
class AuditLog(Base):
    id: int
    event_type: str          # login / api_call / permission_change / data_change / security
    event_action: str        # create / read / update / delete / login / logout
    actor_id: str            # 用户ID
    actor_role: str          # 用户角色
    target_type: str         # 操作对象类型
    target_id: str           # 操作对象ID
    ip_address: str          # 客户端IP
    user_agent: str          # UA
    request_id: str          # X-Request-Id
    trace_id: str            # X-Trace-Id
    timestamp: datetime      # UTC
    status: str              # success / failure
    details: json            # 扩展信息
```

## 存储策略

- **热数据**: PostgreSQL（最近 30 天）
- **冷数据**: 每日归档到 Parquet / S3
- **保留期**: 90 天在线，1 年离线归档

## 关键事件触发点

| 事件 | 触发位置 |
|------|----------|
| 用户登录 | auth/login |
| API 调用 | middleware/auth_middleware |
| 权限变更 | admin/role_management |
| 数据删除 | repository/delete |
| 配置修改 | config/save |
| 异常访问 | error_handler |
