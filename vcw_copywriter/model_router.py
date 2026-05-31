"""
多模型智能路由模块
支持多个 LLM Endpoint 的自动切换和负载均衡
"""
import time
from typing import List, Dict, Optional, Tuple, Iterator
from dataclasses import dataclass


try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


@dataclass
class EndpointStatus:
    """Endpoint 健康状态"""
    name: str
    api_key: str
    base_url: str
    model: str
    priority: int = 0  # 数字越小优先级越高
    total_calls: int = 0
    success_calls: int = 0
    fail_calls: int = 0
    last_fail_time: Optional[float] = None
    last_error: str = ""
    disabled_until: float = 0  # 临时禁用直到此时间戳
    
    @property
    def is_available(self) -> bool:
        """检查当前是否可用"""
        if time.time() < self.disabled_until:
            return False
        # 如果连续失败3次以上，冷却30秒
        if self.fail_calls >= 3 and self.last_fail_time:
            if time.time() - self.last_fail_time < 30:
                return False
        return True
    
    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return self.success_calls / self.total_calls
    
    def record_success(self):
        self.total_calls += 1
        self.success_calls += 1
    
    def record_fail(self, error: str):
        self.total_calls += 1
        self.fail_calls += 1
        self.last_fail_time = time.time()
        self.last_error = error
        # 连续失败过多，临时禁用
        if self.fail_calls >= 5:
            self.disabled_until = time.time() + 60


class ModelRouter:
    """
    多模型智能路由器
    
    功能：
    1. 维护多个 LLM endpoint，按优先级自动切换
    2. 记录每个 endpoint 的健康状态
    3. 支持流式输出
    4. 支持自动降级：temperature/system role 不兼容时自动调整
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.endpoints: List[EndpointStatus] = []
        self._init_endpoints()
        self._current_idx = 0
    
    def _init_endpoints(self):
        """从配置初始化 endpoint 列表"""
        endpoints_cfg = self.config.get("endpoints", [])
        
        # 兼容旧配置（单 endpoint）
        if not endpoints_cfg and self.config.get("api_key"):
            endpoints_cfg = [{
                "name": "default",
                "api_key": self.config.get("api_key", ""),
                "base_url": self.config.get("base_url", ""),
                "model": self.config.get("model", "gpt-4o"),
                "priority": 0
            }]
        
        for i, cfg in enumerate(endpoints_cfg):
            ep = EndpointStatus(
                name=cfg.get("name", f"endpoint_{i}"),
                api_key=cfg.get("api_key", ""),
                base_url=cfg.get("base_url", ""),
                model=cfg.get("model", "gpt-4o"),
                priority=cfg.get("priority", i)
            )
            self.endpoints.append(ep)
        
        # 按优先级排序
        self.endpoints.sort(key=lambda e: e.priority)
    
    def get_available_endpoints(self) -> List[EndpointStatus]:
        """获取当前可用的 endpoint 列表（按优先级排序）"""
        return [ep for ep in self.endpoints if ep.is_available]
    
    def _create_client(self, endpoint: EndpointStatus):
        """为指定 endpoint 创建 OpenAI 客户端"""
        if not HAS_OPENAI:
            raise ImportError("未安装 openai 包")
        kwargs = {"api_key": endpoint.api_key}
        if endpoint.base_url:
            kwargs["base_url"] = endpoint.base_url
        return openai.OpenAI(**kwargs)  # type: ignore[arg-type]
    
    def generate(self, system_prompt: str, user_prompt: str,
                 temperature: float = 0.7, max_tokens: int = 2000,
                 retry_count: int = 2, use_stream: bool = False) -> Tuple[bool, str, str]:
        """
        智能路由生成（非流式）
        
        Returns:
            (success, content, meta)
        """
        if use_stream:
            raise ValueError("流式模式请调用 generate_stream()")
        
        available = self.get_available_endpoints()
        if not available:
            # 全部不可用，尝试重置状态
            for ep in self.endpoints:
                ep.disabled_until = 0
            available = self.get_available_endpoints()
            if not available:
                return False, "", "所有模型端点暂时不可用，请检查配置和网络"
        
        last_error = ""
        
        for endpoint in available:
            temp = temperature
            use_system = True
            
            for attempt in range(retry_count + 1):
                try:
                    client = self._create_client(endpoint)
                    
                    if use_system:
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ]
                    else:
                        messages = [
                            {"role": "user", "content": f"{system_prompt}\n\n---\n\n{user_prompt}"}
                        ]
                    
                    response = client.chat.completions.create(
                        model=endpoint.model,
                        messages=messages,
                        temperature=temp,
                        max_tokens=max_tokens
                    )
                    
                    msg = response.choices[0].message
                    content = msg.content or ""
                    if not content and hasattr(msg, "reasoning_content"):
                        content = msg.reasoning_content or ""
                    
                    tokens = response.usage.total_tokens if response.usage else "N/A"
                    meta = f"模型: {endpoint.model}({endpoint.name}) | Tokens: {tokens}"
                    
                    if content and content.strip():
                        endpoint.record_success()
                        return True, content, meta
                    else:
                        if use_system and attempt == 0:
                            use_system = False
                            continue
                        endpoint.record_fail("空内容")
                        last_error = f"[{endpoint.name}] 返回空内容"
                        break
                
                except Exception as e:
                    err_str = str(e).lower()
                    
                    # temperature 不兼容，自动降级
                    if "invalid temperature" in err_str or "only 1 is allowed" in err_str:
                        if temp != 1:
                            temp = 1
                            continue
                    
                    # system role 不兼容
                    if "system" in err_str and use_system:
                        use_system = False
                        continue
                    
                    if attempt < retry_count:
                        time.sleep(2 ** attempt)
                    else:
                        endpoint.record_fail(str(e))
                        last_error = f"[{endpoint.name}] {e}"
                        break
        
        return False, "", f"所有端点尝试失败。最后错误: {last_error}"
    
    def generate_stream(self, system_prompt: str, user_prompt: str,
                        temperature: float = 0.7, max_tokens: int = 2000) -> Iterator[Tuple[bool, str, str]]:
        """
        流式生成，逐字返回内容
        
        Yields:
            (is_meta, content, meta_info)
            is_meta=True 时，content 是元信息（如使用的模型名）
            is_meta=False 时，content 是文本片段
        """
        available = self.get_available_endpoints()
        if not available:
            for ep in self.endpoints:
                ep.disabled_until = 0
            available = self.get_available_endpoints()
            if not available:
                yield False, "", "所有模型端点暂时不可用"
                return
        
        for endpoint in available:
            temp = temperature
            use_system = True
            
            for attempt in range(3):
                try:
                    client = self._create_client(endpoint)
                    
                    if use_system:
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ]
                    else:
                        messages = [
                            {"role": "user", "content": f"{system_prompt}\n\n---\n\n{user_prompt}"}
                        ]
                    
                    stream = client.chat.completions.create(
                        model=endpoint.model,
                        messages=messages,
                        temperature=temp,
                        max_tokens=max_tokens,
                        stream=True
                    )
                    
                    # 先返回元信息
                    yield True, f"model:{endpoint.model}|endpoint:{endpoint.name}", ""
                    
                    full_content = ""
                    for chunk in stream:
                        delta = chunk.choices[0].delta
                        text = delta.content or ""
                        if not text and hasattr(delta, "reasoning_content"):
                            text = delta.reasoning_content or ""
                        if text:
                            full_content += text
                            yield False, text, ""
                    
                    # 流结束，返回完整内容的元信息
                    yield True, f"done|len:{len(full_content)}", ""
                    endpoint.record_success()
                    return
                
                except Exception as e:
                    err_str = str(e).lower()
                    if "invalid temperature" in err_str and temp != 1:
                        temp = 1
                        continue
                    if "system" in err_str and use_system:
                        use_system = False
                        continue
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                    else:
                        endpoint.record_fail(str(e))
                        break
        
        yield False, "", "所有端点流式生成失败"
    
    def get_status(self) -> List[Dict]:
        """获取所有 endpoint 的状态报告"""
        return [{
            "name": ep.name,
            "model": ep.model,
            "priority": ep.priority,
            "available": ep.is_available,
            "total_calls": ep.total_calls,
            "success_rate": f"{ep.success_rate:.0%}",
            "last_error": ep.last_error[:100] if ep.last_error else "",
        } for ep in self.endpoints]
