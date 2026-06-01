"""
Flask 应用容器 —— 基于 dependency-injector 的依赖注入

设计原则：
  1. 所有服务通过 dependency-injector 的 providers.Singleton 统一管理。
  2. 禁止直接 import 模块级全局变量（如 from app.services.app_services import config）。
  3. 视图函数中通过 get_container() 或 get_service() 获取依赖。
  4. 测试时可通过 container.config.override(...) 等替换任意依赖。

使用示例：
    from app.core.container import get_service
    config = get_service("config")
    memory_bank = get_service("memory_bank")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from dependency_injector import containers, providers

if TYPE_CHECKING:
    from vcw_copywriter.config import Config
    from vcw_copywriter.memory import MemoryBank
    from vcw_copywriter.trend_db import TrendDatabase
    from vcw_copywriter.editor import EditorWorkflow
    from vcw_copywriter.viral_analyzer import ViralAnalyzer
    from services.editor_service import EditorService
    from services.generation_service import GenerationService
    from services.prompt_service import PromptService
    from services.scheduler_service import SchedulerService
    from services.history_service import HistoryService


# ------------------------------------------------------------------------------
# 工厂函数（在容器类外部定义，避免循环导入）
# ------------------------------------------------------------------------------
def _make_config() -> "Config":
    """创建配置单例（含环境变量覆盖）"""
    from vcw_copywriter.config import Config, ensure_dirs

    ensure_dirs()
    Path("data/edited").mkdir(exist_ok=True)

    cfg = Config("config.json")
    if not Path("config.json").exists():
        cfg.save()

    env_overrides = {
        "VCW_API_KEY": ("llm", "api_key"),
        "VCW_BASE_URL": ("llm", "base_url"),
        "VCW_MODEL": ("llm", "model"),
    }
    for env_key, (section, key) in env_overrides.items():
        val = os.environ.get(env_key)
        if val:
            cfg.set(section, key, value=val)
    return cfg


def _make_memory_bank(config: "Config") -> "MemoryBank":
    """创建记忆库单例"""
    from vcw_copywriter.memory import MemoryBank

    db_path = config.get("memory", "db_path", default="data/memory_db.json")
    return MemoryBank(db_path)


def _make_trend_db() -> "TrendDatabase":
    """创建热点数据库单例"""
    from vcw_copywriter.trend_db import TrendDatabase

    return TrendDatabase("data/trend_db.json")


def _make_editor() -> "EditorWorkflow":
    """创建编辑器工作流单例"""
    from vcw_copywriter.editor import EditorWorkflow

    return EditorWorkflow("data/edited")


def _make_scheduler() -> Any:
    """创建调度器单例"""
    from vcw_copywriter.scheduler import get_scheduler

    return get_scheduler()


def _make_viral_analyzer() -> "ViralAnalyzer":
    """创建爆款分析器单例"""
    from vcw_copywriter.viral_analyzer import ViralAnalyzer

    return ViralAnalyzer()


def _make_transaction_manager():
    """创建事务管理器单例"""
    from services.base.transaction_manager import TransactionManager

    return TransactionManager()


def _make_permission_manager(config: "Config"):
    """创建权限管理器单例"""
    from services.base.permission_manager import PermissionManager

    return PermissionManager(config)


def _make_llm_gateway(config: "Config"):
    """创建 LLM Gateway 单例。

    根据 config.json 中的 llm 配置注册 provider adapter，
    并挂载 tracing、metrics、fallback 中间件。
    """
    from llm.gateway.llm_gateway import LLMGateway, ProviderRegistry, GatewayConfig
    from llm.adapter import create_adapter
    from llm.fallback.chain_strategy import ChainFallbackStrategy
    from llm.metrics.token_accounting import TokenAccountingCollector
    from llm.tracing.otel_tracing import OtelTracingMiddleware

    llm_config = config.get("llm") or {}
    registry = ProviderRegistry()

    # 主 provider
    provider = llm_config.get("provider", "openai")
    api_key = llm_config.get("api_key", "")
    base_url = llm_config.get("base_url", "")
    model = llm_config.get("model", "gpt-4o")

    if api_key:
        adapter = create_adapter(
            provider,
            api_key=api_key,
            base_url=base_url or None,
            model=model,
        )
        registry.register(provider, adapter)

    # endpoints（多模型路由配置）
    endpoints = llm_config.get("endpoints", [])
    for ep in endpoints:
        ep_name = ep.get("name", provider)
        ep_api_key = ep.get("api_key", api_key)
        ep_base_url = ep.get("base_url", base_url)
        ep_model = ep.get("model", model)
        if ep_api_key:
            adapter = create_adapter(
                ep_name,
                api_key=ep_api_key,
                base_url=ep_base_url or None,
                model=ep_model,
            )
            registry.register(ep_name, adapter)

    gateway_config = GatewayConfig(
        default_provider=provider,
        fallback_enabled=len(endpoints) > 1,
        fallback_providers=[ep.get("name") for ep in endpoints],
        metrics_enabled=True,
        tracing_enabled=True,
    )

    gateway = LLMGateway(config=gateway_config, registry=registry)
    gateway.attach_metrics(TokenAccountingCollector())
    gateway.attach_tracing(OtelTracingMiddleware())

    if len(endpoints) > 1:
        gateway.attach_fallback(
            ChainFallbackStrategy(priority=[ep.get("name") for ep in endpoints])
        )

    return gateway


# ---- Repository factories ----

def _make_copy_repo():
    from domains.generation.infrastructure.repository import CopyRepository
    return CopyRepository()



def _make_memory_repo(memory_bank):
    from domains.generation.infrastructure.repository import MemoryRepository
    return MemoryRepository(memory_bank)


def _make_draft_repo(editor):
    from domains.editor.infrastructure.repository import DraftRepository
    return DraftRepository(editor)


def _make_template_repo():
    from domains.prompt.infrastructure.repository import PromptTemplateRepository
    return PromptTemplateRepository()


def _make_knowledge_repo():
    from domains.prompt.infrastructure.repository import KnowledgeRepository
    return KnowledgeRepository()


def _make_trend_repo(trend_db):
    from domains.trend.infrastructure.repository import TrendRepository
    return TrendRepository(trend_db)


def _make_scheduler_repo(scheduler):
    from domains.trend.infrastructure.repository import SchedulerRepository
    return SchedulerRepository(scheduler)


# ---- Service factories ----

def _make_generation_client(generation_service):
    """创建进程内 GenerationService 客户端适配器"""
    from clients.inprocess_generation_client import InProcessGenerationClient

    return InProcessGenerationClient(generation_service)


def _make_editor_service(
    draft_repo,
    config,
    generation_client,
    transaction_manager,
    permission_manager,
) -> "EditorService":
    """创建编辑器服务单例"""
    from services.editor_service import EditorService

    return EditorService(
        draft_repo, config, generation_client, transaction_manager, permission_manager
    )


def _make_generation_service(
    config, copy_repo, memory_repo, draft_repo, transaction_manager, permission_manager, llm_gateway=None
) -> "GenerationService":
    """创建文案生成服务单例"""
    from services.generation_service import GenerationService

    return GenerationService(
        config, copy_repo, memory_repo, draft_repo, transaction_manager, permission_manager, llm_gateway=llm_gateway
    )


def _make_async_task_service(permission_manager):
    """创建异步任务服务单例"""
    from services.async_task_service import AsyncTaskService

    return AsyncTaskService(permission_manager=permission_manager)


def _make_prompt_service(
    template_repo,
    knowledge_repo,
    config,
    transaction_manager,
    permission_manager,
) -> "PromptService":
    """创建 Prompt 服务单例"""
    from services.prompt_service import PromptService

    return PromptService(
        template_repo=template_repo,
        knowledge_repo=knowledge_repo,
        config=config,
        transaction_manager=transaction_manager,
        permission_manager=permission_manager,
    )


def _make_scheduler_service(
    config,
    scheduler_repo,
    trend_repo,
    transaction_manager,
    permission_manager,
) -> "SchedulerService":
    """创建调度器服务单例"""
    from services.scheduler_service import SchedulerService

    return SchedulerService(
        config=config,
        scheduler_repo=scheduler_repo,
        trend_repo=trend_repo,
        transaction_manager=transaction_manager,
        permission_manager=permission_manager,
    )


def _make_history_service(
    config,
    copy_repo,
    transaction_manager,
    permission_manager,
) -> "HistoryService":
    """创建历史记录服务单例"""
    from services.history_service import HistoryService

    return HistoryService(
        config=config,
        copy_repo=copy_repo,
        transaction_manager=transaction_manager,
        permission_manager=permission_manager,
    )


def _make_generation_handler(generation_service, async_task_service, history_service):
    from domains.generation.application import GenerationHandler

    return GenerationHandler(generation_service, async_task_service, history_service)


def _make_editor_handler(editor_service):
    from domains.editor.application import EditorHandler

    return EditorHandler(editor_service)


def _make_prompt_handler(prompt_service):
    from domains.prompt.application import PromptHandler

    return PromptHandler(prompt_service)


def _make_trend_handler(scheduler_service):
    from domains.trend.application import TrendHandler

    return TrendHandler(scheduler_service)


# ------------------------------------------------------------------------------
# 声明式容器
# ------------------------------------------------------------------------------
class AppContainer(containers.DeclarativeContainer):
    """
    应用级依赖注入容器。

    在 Flask Application Factory 中实例化并挂载到 ``app.container``，
    供视图函数、CLI 命令、后台任务统一使用。
    """

    # ---- 配置（单例） ----
    config = providers.Singleton(_make_config)

    # ---- 事务管理器（单例） ----
    transaction_manager = providers.Singleton(_make_transaction_manager)

    # ---- 权限管理器（单例，依赖 config） ----
    permission_manager = providers.Singleton(_make_permission_manager, config=config)

    # ---- 记忆库（单例，依赖 config） ----
    memory_bank = providers.Singleton(_make_memory_bank, config=config)

    # ---- 热点数据库（单例） ----
    trend_db = providers.Singleton(_make_trend_db)

    # ---- 编辑器工作流（单例） ----
    editor = providers.Singleton(_make_editor)

    # ---- 调度器（单例） ----
    scheduler = providers.Singleton(_make_scheduler)

    # ---- 爆款分析器（单例） ----
    viral_analyzer = providers.Singleton(_make_viral_analyzer)

    # ---- LLM Gateway（单例） ----
    llm_gateway = providers.Singleton(_make_llm_gateway, config=config)

    # ---- Repositories（单例） ----
    copy_repo = providers.Singleton(_make_copy_repo)
    memory_repo = providers.Singleton(_make_memory_repo, memory_bank=memory_bank)
    draft_repo = providers.Singleton(_make_draft_repo, editor=editor)
    template_repo = providers.Singleton(_make_template_repo)
    knowledge_repo = providers.Singleton(_make_knowledge_repo)
    trend_repo = providers.Singleton(_make_trend_repo, trend_db=trend_db)
    scheduler_repo = providers.Singleton(_make_scheduler_repo, scheduler=scheduler)

    # ---- 文案生成服务（单例） ----
    generation_service = providers.Singleton(
        _make_generation_service,
        config=config,
        copy_repo=copy_repo,
        memory_repo=memory_repo,
        draft_repo=draft_repo,
        transaction_manager=transaction_manager,
        permission_manager=permission_manager,
        llm_gateway=llm_gateway,
    )

    # ---- 生成服务客户端（单例，进程内适配器） ----
    generation_client = providers.Singleton(
        _make_generation_client,
        generation_service=generation_service,
    )

    # ---- 编辑器服务（单例） ----
    editor_service = providers.Singleton(
        _make_editor_service,
        draft_repo=draft_repo,
        config=config,
        generation_client=generation_client,
        transaction_manager=transaction_manager,
        permission_manager=permission_manager,
    )

    # ---- Prompt 服务（单例） ----
    prompt_service = providers.Singleton(
        _make_prompt_service,
        template_repo=template_repo,
        knowledge_repo=knowledge_repo,
        config=config,
        transaction_manager=transaction_manager,
        permission_manager=permission_manager,
    )

    # ---- 调度器服务（单例） ----
    scheduler_service = providers.Singleton(
        _make_scheduler_service,
        config=config,
        scheduler_repo=scheduler_repo,
        trend_repo=trend_repo,
        transaction_manager=transaction_manager,
        permission_manager=permission_manager,
    )

    # ---- 历史记录服务（单例） ----
    history_service = providers.Singleton(
        _make_history_service,
        config=config,
        copy_repo=copy_repo,
        transaction_manager=transaction_manager,
        permission_manager=permission_manager,
    )

    # ---- 异步任务服务（单例） ----
    async_task_service = providers.Singleton(
        _make_async_task_service,
        permission_manager=permission_manager,
    )

    # ---- Application handlers ----
    generation_handler = providers.Singleton(
        _make_generation_handler,
        generation_service=generation_service,
        async_task_service=async_task_service,
        history_service=history_service,
    )
    editor_handler = providers.Singleton(
        _make_editor_handler,
        editor_service=editor_service,
    )
    prompt_handler = providers.Singleton(
        _make_prompt_handler,
        prompt_service=prompt_service,
    )
    trend_handler = providers.Singleton(
        _make_trend_handler,
        scheduler_service=scheduler_service,
    )


# ------------------------------------------------------------------------------
# 全局容器句柄（仅在应用初始化后有效）
# ------------------------------------------------------------------------------
_container: Optional[AppContainer] = None


def set_container(container: AppContainer) -> None:
    """在应用初始化时设置全局容器句柄（供无请求上下文场景使用）。"""
    global _container
    _container = container


def get_container() -> AppContainer:
    """
    获取当前应用容器。

    优先尝试从 Flask ``current_app`` 获取（需在应用/请求上下文中）。
    若不在 Flask 上下文中（如后台线程、测试 setup），则回退到全局句柄。

    Raises:
        RuntimeError: 容器尚未初始化。
    """
    try:
        from flask import current_app, has_app_context, has_request_context

        if has_app_context() or has_request_context():
            return current_app.container  # type: ignore[attr-defined]
    except (ImportError, AttributeError, RuntimeError):
        pass

    if _container is not None:
        return _container

    raise RuntimeError(
        "应用容器尚未初始化。"
        "请确保 create_app() 中已执行 app.container = container，"
        "或在测试环境中先调用 set_container(container)。"
    )


def get_service(name: str) -> Any:
    """
    快捷获取已注册的服务实例。

    通过 provider 名称访问容器中的 Singleton/Factory，
    首次调用时触发实例化，后续调用返回缓存实例。

    Example:
        from app.core.container import get_service
        config = get_service("config")
        memory_bank = get_service("memory_bank")
    """
    provider = getattr(get_container(), name, None)
    if provider is None:
        raise KeyError(f"容器中未注册服务 '{name}'")
    return provider()
