# OpenAPI / Swagger 集成指南

## 访问地址

启动应用后访问：
- Swagger UI: `http://127.0.0.1:5000/apidocs`
- OpenAPI JSON: `http://127.0.0.1:5000/apispec_1.json`

## API 注释规范

在路由函数 docstring 中使用 YAML 格式：

```python
@bp.route("/generate/async", methods=["POST"])
def generate_async():
    """
    提交异步文案生成任务
    ---
    tags:
      - Generation
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            prompt:
              type: string
              example: "港籍学生升读内地大学"
            model:
              type: string
              example: "gpt-4o"
    responses:
      202:
        description: 任务已接受
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                task_id:
                  type: string
      401:
        description: 未授权
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
```

## 公共端点（无需认证）

以下端点在 Swagger 中标记为 public：
- `GET /api/v1/model/status`
- `GET /health`
- `GET /metrics`

## 前端使用

从 `/apispec_1.json` 可生成 TypeScript 类型：

```bash
npx openapi-typescript http://127.0.0.1:5000/apispec_1.json -o vcw-api.ts
```
