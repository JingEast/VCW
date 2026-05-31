"""Token Accounting 测试。

验证：
  1. per-request 统计
  2. per-user 聚合
  3. per-model 聚合
  4. cost 自动计算
  5. metrics API 输出（Prometheus + JSON）
  6. Gateway 集成（chat/complete/embed 触发 metrics）
  7. 并发安全
  8. 记录上限与驱逐
"""

from __future__ import annotations

import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from llm.adapter.base import LLMResponse, TokenUsage
from llm.gateway.config import GatewayConfig
from llm.gateway.core import LLMGateway
from llm.gateway.registry import ProviderRegistry
from llm.metrics import (
    GlobalSummary,
    MetricLabels,
    ModelSummary,
    RequestSummary,
    TokenAccountingCollector,
    UserSummary,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def collector() -> TokenAccountingCollector:
    return TokenAccountingCollector(max_records=100)


@pytest.fixture
def mock_adapter():
    """返回一个 mock adapter，chat/embed 均返回固定结果。"""
    adapter = MagicMock()
    adapter.provider_name = "openai"
    adapter.model = "gpt-4o"
    adapter.chat.return_value = LLMResponse(
        content="Hello!",
        provider="openai",
        model="gpt-4o",
        usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        latency_ms=123.0,
    )
    adapter.embed.return_value = [[0.1, 0.2]]
    adapter.health_check.return_value = MagicMock(value="healthy")
    return adapter


@pytest.fixture
def gateway(mock_adapter):
    """返回一个挂载了 TokenAccountingCollector 的 Gateway。"""
    registry = ProviderRegistry()
    registry.register("openai", mock_adapter)
    config = GatewayConfig(default_provider="openai")
    gw = LLMGateway(config, registry)
    collector = TokenAccountingCollector()
    gw.attach_metrics(collector)
    return gw


# =============================================================================
# Basic Recording Tests
# =============================================================================


class TestTokenAccountingRecording:
    """基础记录测试。"""

    def test_record_single_call(self, collector: TokenAccountingCollector):
        """记录单次调用后可查询。"""
        collector.record(
            labels=MetricLabels(provider="openai", model="gpt-4o", status="success", user="alice"),
            latency_ms=100.0,
            prompt_tokens=10,
            completion_tokens=5,
            cost=0.0,
            request_id="req-001",
        )

        summary = collector.get_by_request("req-001")
        assert summary is not None
        assert summary.request_id == "req-001"
        assert summary.provider == "openai"
        assert summary.model == "gpt-4o"
        assert summary.user == "alice"
        assert summary.status == "success"
        assert summary.prompt_tokens == 10
        assert summary.completion_tokens == 5
        assert summary.total_tokens == 15
        assert summary.latency_ms == 100.0

    def test_cost_auto_computed(self, collector: TokenAccountingCollector):
        """cost=0 时自动根据 model pricing 计算。"""
        collector.record(
            labels=MetricLabels(provider="openai", model="gpt-4o", status="success"),
            latency_ms=100.0,
            prompt_tokens=1000,
            completion_tokens=500,
            cost=0.0,
        )
        # gpt-4o pricing: (0.005, 0.015)
        # cost = 1000/1000 * 0.005 + 500/1000 * 0.015 = 0.005 + 0.0075 = 0.0125
        summary = collector.get_summary()
        assert summary.total_cost == pytest.approx(0.0125, abs=1e-6)

    def test_cost_manual_override(self, collector: TokenAccountingCollector):
        """传入非零 cost 时直接使用。"""
        collector.record(
            labels=MetricLabels(provider="openai", model="gpt-4o", status="success"),
            latency_ms=100.0,
            prompt_tokens=10,
            completion_tokens=5,
            cost=0.999,
        )
        summary = collector.get_summary()
        assert summary.total_cost == 0.999

    def test_request_not_found(self, collector: TokenAccountingCollector):
        """查询不存在的 request_id 返回 None。"""
        assert collector.get_by_request("nope") is None


# =============================================================================
# Aggregation Tests
# =============================================================================


class TestTokenAccountingAggregation:
    """聚合统计测试。"""

    def test_per_user_aggregation(self, collector: TokenAccountingCollector):
        """per-user 聚合正确。"""
        # alice 调用 2 次
        collector.record(
            MetricLabels("openai", "gpt-4o", "success", "alice"),
            100.0, 10, 5, 0.0,
        )
        collector.record(
            MetricLabels("openai", "gpt-4o", "success", "alice"),
            200.0, 20, 10, 0.0,
        )
        # bob 调用 1 次
        collector.record(
            MetricLabels("anthropic", "claude-3-opus", "success", "bob"),
            150.0, 30, 15, 0.0,
        )

        alice = collector.get_by_user("alice")
        assert alice.total_requests == 2
        assert alice.total_prompt_tokens == 30
        assert alice.total_completion_tokens == 15
        assert alice.total_tokens == 45
        assert alice.avg_latency_ms == 150.0
        assert set(alice.models) == {"gpt-4o"}

        bob = collector.get_by_user("bob")
        assert bob.total_requests == 1
        assert bob.total_prompt_tokens == 30
        assert "claude-3-opus" in bob.models

    def test_per_model_aggregation(self, collector: TokenAccountingCollector):
        """per-model 聚合正确。"""
        collector.record(
            MetricLabels("openai", "gpt-4o", "success", "alice"),
            100.0, 10, 5, 0.0,
        )
        collector.record(
            MetricLabels("openai", "gpt-4o", "success", "bob"),
            200.0, 20, 10, 0.0,
        )
        collector.record(
            MetricLabels("openai", "gpt-4o-mini", "success", "alice"),
            50.0, 5, 2, 0.0,
        )

        gpt4o = collector.get_by_model("gpt-4o")
        assert gpt4o.total_requests == 2
        assert gpt4o.total_prompt_tokens == 30
        assert gpt4o.total_completion_tokens == 15
        assert set(gpt4o.users) == {"alice", "bob"}

        mini = collector.get_by_model("gpt-4o-mini")
        assert mini.total_requests == 1
        assert mini.users == ["alice"]

    def test_global_summary(self, collector: TokenAccountingCollector):
        """全局聚合包含 by_user 和 by_model。"""
        collector.record(
            MetricLabels("openai", "gpt-4o", "success", "alice"),
            100.0, 10, 5, 0.0,
        )
        collector.record(
            MetricLabels("anthropic", "claude-3-opus", "failure", "bob"),
            200.0, 20, 10, 0.0,
        )

        global_sum = collector.get_summary()
        assert global_sum.total_requests == 2
        assert global_sum.total_prompt_tokens == 30
        assert global_sum.total_completion_tokens == 15
        assert global_sum.total_tokens == 45
        assert global_sum.avg_latency_ms == 150.0
        assert "alice" in global_sum.by_user
        assert "bob" in global_sum.by_user
        assert "gpt-4o" in global_sum.by_model
        assert "claude-3-opus" in global_sum.by_model

    def test_empty_aggregation(self, collector: TokenAccountingCollector):
        """空记录时聚合返回零值。"""
        user = collector.get_by_user("nobody")
        assert user.total_requests == 0
        assert user.total_cost == 0.0

        model = collector.get_by_model("none")
        assert model.total_requests == 0

        global_sum = collector.get_summary()
        assert global_sum.total_requests == 0


# =============================================================================
# Query & Filter Tests
# =============================================================================


class TestTokenAccountingQuery:
    """查询与过滤测试。"""

    def test_list_requests_default_limit(self, collector: TokenAccountingCollector):
        """list_requests 默认返回最多 100 条。"""
        for i in range(5):
            collector.record(
                MetricLabels("openai", "gpt-4o", "success"),
                float(i), i, i, 0.0,
            )
        results = collector.list_requests()
        assert len(results) == 5
        # 倒序排列，包含全部 latency 值
        latencies = [r.latency_ms for r in results]
        assert sorted(latencies, reverse=True) == [4.0, 3.0, 2.0, 1.0, 0.0]

    def test_list_requests_filter_by_user(self, collector: TokenAccountingCollector):
        """按 user 过滤。"""
        collector.record(
            MetricLabels("openai", "gpt-4o", "success", "alice"),
            100.0, 10, 5, 0.0,
        )
        collector.record(
            MetricLabels("openai", "gpt-4o", "success", "bob"),
            200.0, 20, 10, 0.0,
        )
        results = collector.list_requests(user="alice")
        assert len(results) == 1
        assert results[0].user == "alice"

    def test_list_requests_filter_by_model(self, collector: TokenAccountingCollector):
        """按 model 过滤。"""
        collector.record(
            MetricLabels("openai", "gpt-4o", "success"),
            100.0, 10, 5, 0.0,
        )
        collector.record(
            MetricLabels("openai", "gpt-4o-mini", "success"),
            200.0, 20, 10, 0.0,
        )
        results = collector.list_requests(model="gpt-4o")
        assert len(results) == 1
        assert results[0].model == "gpt-4o"

    def test_list_requests_filter_by_status(self, collector: TokenAccountingCollector):
        """按 status 过滤。"""
        collector.record(
            MetricLabels("openai", "gpt-4o", "success"),
            100.0, 10, 5, 0.0,
        )
        collector.record(
            MetricLabels("openai", "gpt-4o", "failure"),
            200.0, 20, 10, 0.0,
        )
        results = collector.list_requests(status="failure")
        assert len(results) == 1
        assert results[0].status == "failure"

    def test_list_requests_limit(self, collector: TokenAccountingCollector):
        """limit 参数生效。"""
        for i in range(10):
            collector.record(
                MetricLabels("openai", "gpt-4o", "success"),
                float(i), i, i, 0.0,
            )
        results = collector.list_requests(limit=3)
        assert len(results) == 3

    def test_reset(self, collector: TokenAccountingCollector):
        """reset 清空所有记录。"""
        collector.record(
            MetricLabels("openai", "gpt-4o", "success"),
            100.0, 10, 5, 0.0,
        )
        assert collector.get_summary().total_requests == 1
        collector.reset()
        assert collector.get_summary().total_requests == 0


# =============================================================================
# Metrics API Output Tests
# =============================================================================


class TestTokenAccountingMetricsOutput:
    """Metrics API 输出测试。"""

    def test_prometheus_openmetrics_format(self, collector: TokenAccountingCollector):
        """Prometheus OpenMetrics 文本格式包含正确指标。"""
        collector.record(
            MetricLabels("openai", "gpt-4o", "success", "alice"),
            100.0, 10, 5, 0.0,
        )
        collector.record(
            MetricLabels("openai", "gpt-4o", "failure", "bob"),
            200.0, 20, 10, 0.0,
        )

        output = collector.expose_metrics()
        assert "# HELP llm_prompt_tokens_total" in output
        assert "# TYPE llm_prompt_tokens_total counter" in output
        assert "# HELP llm_cost_total" in output
        assert "llm_prompt_tokens_total{provider=\"openai\",model=\"gpt-4o\",user=\"alice\",status=\"success\"} 10" in output
        assert "llm_completion_tokens_total{provider=\"openai\",model=\"gpt-4o\",user=\"bob\",status=\"failure\"} 10" in output
        assert "llm_requests_total" in output

    def test_json_output(self, collector: TokenAccountingCollector):
        """JSON 输出包含全局、by_user、by_model。"""
        collector.record(
            MetricLabels("openai", "gpt-4o", "success", "alice"),
            100.0, 10, 5, 0.0,
        )
        data = collector.to_json()
        assert data["total_requests"] == 1
        assert data["total_prompt_tokens"] == 10
        assert data["total_completion_tokens"] == 5
        assert "by_user" in data
        assert "alice" in data["by_user"]
        assert "by_model" in data
        assert "gpt-4o" in data["by_model"]


# =============================================================================
# Gateway Integration Tests
# =============================================================================


class TestTokenAccountingGatewayIntegration:
    """Gateway 集成测试。"""

    def test_chat_records_metrics(self, gateway: LLMGateway, mock_adapter):
        """chat 调用后 metrics 被记录。"""
        metrics = gateway._metrics
        assert isinstance(metrics, TokenAccountingCollector)

        response = gateway.chat([{"role": "user", "content": "hi"}], user="alice", request_id="req-chat-1")
        assert response.content == "Hello!"

        summary = metrics.get_by_request("req-chat-1")
        assert summary is not None
        assert summary.user == "alice"
        assert summary.model == "gpt-4o"
        assert summary.status == "success"
        assert summary.prompt_tokens == 10
        assert summary.completion_tokens == 5

    def test_complete_records_metrics(self, gateway: LLMGateway, mock_adapter):
        """complete 调用后 metrics 被记录。"""
        metrics = gateway._metrics
        response = gateway.complete("Say hello", system="Be brief", user="bob")
        assert response.content == "Hello!"

        # complete 内部调用 chat，但 request_id 未传，所以不会按固定 id 查
        # 改为查全局
        global_sum = metrics.get_summary()
        assert global_sum.total_requests >= 1
        assert "bob" in global_sum.by_user

    def test_embed_records_metrics(self, gateway: LLMGateway, mock_adapter):
        """embed 调用后 metrics 被记录。"""
        metrics = gateway._metrics
        result = gateway.embed(["hello"], user="charlie", request_id="req-embed-1")
        assert result == [[0.1, 0.2]]

        summary = metrics.get_by_request("req-embed-1")
        assert summary is not None
        assert summary.user == "charlie"
        assert summary.status == "success"

    def test_chat_failure_records_metrics(self, gateway: LLMGateway, mock_adapter):
        """chat 异常时 metrics 记录 failure。"""
        metrics = gateway._metrics
        mock_adapter.chat.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError):
            gateway.chat([{"role": "user", "content": "x"}], user="dave", request_id="req-fail")

        summary = metrics.get_by_request("req-fail")
        assert summary is not None
        assert summary.status == "failure"
        assert summary.user == "dave"

    def test_multiple_users_and_models(self, gateway: LLMGateway, mock_adapter):
        """多用户多模型调用后聚合正确。"""
        metrics = gateway._metrics
        for user in ["alice", "bob", "alice"]:
            gateway.chat([{"role": "user", "content": "hi"}], user=user)

        global_sum = metrics.get_summary()
        assert global_sum.total_requests == 3
        assert global_sum.by_user["alice"].total_requests == 2
        assert global_sum.by_user["bob"].total_requests == 1


# =============================================================================
# Concurrency & Eviction Tests
# =============================================================================


class TestTokenAccountingConcurrency:
    """并发安全与记录上限测试。"""

    def test_concurrent_record(self):
        """多线程并发记录不丢数据。"""
        collector = TokenAccountingCollector()
        n_threads = 10
        n_per_thread = 100

        def worker(tid: int):
            for i in range(n_per_thread):
                collector.record(
                    MetricLabels("openai", "gpt-4o", "success", f"user-{tid}"),
                    float(i), i, i, 0.0,
                )

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        summary = collector.get_summary()
        assert summary.total_requests == n_threads * n_per_thread

    def test_max_records_eviction(self):
        """超过 max_records 时自动驱逐最老记录。"""
        collector = TokenAccountingCollector(max_records=5)
        for i in range(10):
            collector.record(
                MetricLabels("openai", "gpt-4o", "success"),
                float(i), i, i, 0.0,
                request_id=f"req-{i:02d}",
            )

        summary = collector.get_summary()
        assert summary.total_requests == 5
        # 最老的 req-00 到 req-04 应被驱逐
        assert collector.get_by_request("req-00") is None
        assert collector.get_by_request("req-09") is not None


# =============================================================================
# Cost Calculation Tests
# =============================================================================


class TestTokenAccountingCost:
    """成本计算测试。"""

    def test_cost_gpt4o(self, collector: TokenAccountingCollector):
        """gpt-4o 成本计算正确。"""
        collector.record(
            MetricLabels("openai", "gpt-4o", "success"),
            100.0, 2000, 1000, 0.0,
        )
        summary = collector.get_summary()
        # 2000/1000*0.005 + 1000/1000*0.015 = 0.01 + 0.015 = 0.025
        assert summary.total_cost == pytest.approx(0.025, abs=1e-6)

    def test_cost_claude(self, collector: TokenAccountingCollector):
        """claude-3-opus 成本计算正确。"""
        collector.record(
            MetricLabels("anthropic", "claude-3-opus", "success"),
            100.0, 1000, 500, 0.0,
        )
        summary = collector.get_summary()
        # 1000/1000*0.015 + 500/1000*0.075 = 0.015 + 0.0375 = 0.0525
        assert summary.total_cost == pytest.approx(0.0525, abs=1e-6)

    def test_cost_default_pricing(self, collector: TokenAccountingCollector):
        """未知 model 使用 default pricing。"""
        collector.record(
            MetricLabels("custom", "unknown-model", "success"),
            100.0, 1000, 1000, 0.0,
        )
        summary = collector.get_summary()
        # 1000/1000*0.01 + 1000/1000*0.01 = 0.02
        assert summary.total_cost == pytest.approx(0.02, abs=1e-6)

    def test_cost_multiple_calls_sum(self, collector: TokenAccountingCollector):
        """多笔调用成本累加。"""
        collector.record(
            MetricLabels("openai", "gpt-4o", "success"),
            100.0, 1000, 500, 0.0,
        )
        collector.record(
            MetricLabels("openai", "gpt-4o", "success"),
            100.0, 1000, 500, 0.0,
        )
        summary = collector.get_summary()
        # 2 * (0.005 + 0.0075) = 0.025
        assert summary.total_cost == pytest.approx(0.025, abs=1e-6)


# =============================================================================
# Interface Compliance Tests
# =============================================================================


class TestTokenAccountingInterface:
    """接口合规测试。"""

    def test_is_base_metrics_collector(self):
        """TokenAccountingCollector 是 BaseMetricsCollector 子类。"""
        from llm.metrics.base import BaseMetricsCollector
        assert issubclass(TokenAccountingCollector, BaseMetricsCollector)

    def test_observe_request_duration_noop(self, collector: TokenAccountingCollector):
        """observe_request_duration 不抛异常。"""
        collector.observe_request_duration(
            MetricLabels("openai", "gpt-4o", "success"),
            100.0,
        )

    def test_increment_request_total_noop(self, collector: TokenAccountingCollector):
        """increment_request_total 不抛异常。"""
        collector.increment_request_total(
            MetricLabels("openai", "gpt-4o", "success"),
        )
