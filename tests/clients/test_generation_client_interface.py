"""
Generation Service Client Interface 合规测试

验证 IGenerationServiceClient 作为抽象接口的契约：
- 是 ABC
- generate_text 是 abstractmethod
- 未实现子类无法实例化
"""

import pytest
from abc import ABC

from interfaces.generation_client import IGenerationServiceClient


def test_is_abstract_base_class():
    assert issubclass(IGenerationServiceClient, ABC)


def test_generate_text_is_abstract():
    assert getattr(IGenerationServiceClient.generate_text, "__isabstractmethod__", False)


def test_cannot_instantiate_directly():
    with pytest.raises(TypeError):
        IGenerationServiceClient()


def test_unimplemented_subclass_cannot_instantiate():
    class BrokenClient(IGenerationServiceClient):
        pass

    with pytest.raises(TypeError):
        BrokenClient()


def test_implemented_subclass_can_instantiate():
    class WorkingClient(IGenerationServiceClient):
        def generate_text(self, system_prompt: str, user_prompt: str):
            return (True, "ok", "")

    client = WorkingClient()
    result = client.generate_text("sys", "user")
    assert result == (True, "ok", "")
