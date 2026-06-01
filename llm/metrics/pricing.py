"""LLM 模型定价与成本计算。

本模块位于 llm/ 层，供 prompt_runtime 和 token_accounting 复用，
避免 llm -> prompt_runtime 的反向依赖。
"""

from __future__ import annotations

from typing import Dict, Tuple

MODEL_PRICING: Dict[str, Tuple[float, float]] = {
    # (input_price_per_1k, output_price_per_1k)
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.01, 0.03),
    "moonshot-v1-8k": (0.012, 0.012),
    "moonshot-v1-32k": (0.024, 0.024),
    "claude-3-opus": (0.015, 0.075),
    "claude-3-sonnet": (0.003, 0.015),
    "claude-3-haiku": (0.00025, 0.00125),
    "default": (0.01, 0.01),
}


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """根据 model 和 token 数计算成本（USD）。"""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
    input_price, output_price = pricing
    cost = (input_tokens / 1000.0) * input_price + (output_tokens / 1000.0) * output_price
    return round(cost, 6)
