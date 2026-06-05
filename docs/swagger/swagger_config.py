"""Swagger / OpenAPI Configuration.

Integrates flasgger with Flask Application Factory.
Provides auto-generated API docs from docstrings.
"""

from typing import Any

from flask import Flask
from flasgger import Swagger

SWAGGER_TEMPLATE: dict[str, Any] = {
    "swagger": "2.0",
    "info": {
        "title": "VCW API",
        "description": "港籍升学热点文案批量生成器 - REST API 文档",
        "version": "1.0.0",
        "contact": {
            "name": "VCW Team",
            "url": "https://github.com/JingEast/VCW",
        },
    },
    "basePath": "/api/v1",
    "schemes": ["http", "https"],
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT Token. Example: Bearer <your_token>",
        }
    },
    "tags": [
        {"name": "Generation", "description": "文案生成接口（流式/异步/批量）"},
        {"name": "Editor", "description": "文案编辑与去 AI 化"},
        {"name": "Prompts", "description": "Prompt 模板管理"},
        {"name": "Trends", "description": "热点趋势与调度器"},
        {"name": "Misc", "description": "模型状态与文件预览"},
    ],
}

SWAGGER_CONFIG: dict[str, Any] = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec_1",
            "route": "/apispec_1.json",
            "rule_filter": lambda rule: rule.endpoint.startswith("api_v1"),
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs",
}


def init_swagger(app: Flask) -> None:
    """Register Swagger on the Flask app."""
    Swagger(app, config=SWAGGER_CONFIG, template=SWAGGER_TEMPLATE)
