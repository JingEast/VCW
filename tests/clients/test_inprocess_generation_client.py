"""
InProcessGenerationClient 单元测试

验证进程内适配器正确委托到 GenerationService，
满足 IGenerationServiceClient 接口契约。
"""

from typing import Tuple

from clients.inprocess_generation_client import InProcessGenerationClient
from interfaces.generation_client import IGenerationServiceClient


class FakeGenerationService:
    """伪 GenerationService，用于隔离测试。"""

    def __init__(self, response: Tuple[bool, str, str] = (True, "generated", "meta")):
        self.calls = []
        self._response = response

    def generate_text(self, system_prompt: str, user_prompt: str) -> Tuple[bool, str, str]:
        self.calls.append((system_prompt, user_prompt))
        return self._response


def test_implements_interface():
    svc = FakeGenerationService()
    client = InProcessGenerationClient(svc)
    assert isinstance(client, IGenerationServiceClient)


def test_delegates_generate_text_success():
    svc = FakeGenerationService(response=(True, "润色结果", "ok"))
    client = InProcessGenerationClient(svc)

    success, text, meta = client.generate_text(
        system_prompt="sys",
        user_prompt="user",
    )

    assert success is True
    assert text == "润色结果"
    assert meta == "ok"
    assert svc.calls == [("sys", "user")]


def test_delegates_generate_text_failure():
    svc = FakeGenerationService(response=(False, "", "rate limited"))
    client = InProcessGenerationClient(svc)

    success, text, meta = client.generate_text(
        system_prompt="sys",
        user_prompt="user",
    )

    assert success is False
    assert text == ""
    assert meta == "rate limited"


def test_passes_prompts_verbatim():
    svc = FakeGenerationService()
    client = InProcessGenerationClient(svc)

    client.generate_text("system_提示", "user_提示")

    assert svc.calls[0] == ("system_提示", "user_提示")
