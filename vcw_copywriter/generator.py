"""
文案生成模块
封装LLM API调用，支持多种Provider（OpenAI, DeepSeek, Kimi等）
新增：多模型智能路由、流式生成、异步任务
"""
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple, Iterator


try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class CopywriterGenerator:
    """文案生成器（向后兼容旧版单模型模式）"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.provider = config.get("provider", "openai")
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "")
        self.model = config.get("model", "gpt-4o")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 2000)
        self.client: Any = None
        
        if not self.api_key:
            raise ValueError("API Key未设置，请在config.json中配置llm.api_key")
        
        self._init_client()
    
    def _init_client(self):
        """初始化OpenAI兼容客户端"""
        if not HAS_OPENAI:
            raise ImportError(
                "未安装openai包。请运行: pip install openai>=1.0.0"
            )
        
        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        
        self.client = openai.OpenAI(**client_kwargs)
    
    def generate(self, system_prompt: str, user_prompt: str,
                 retry_count: int = 2) -> Tuple[bool, str, str]:
        """
        调用LLM生成文案（向后兼容）
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            retry_count: 失败重试次数
        
        Returns:
            (success: bool, content: str, meta_info: str)
        """
        temperature = self.temperature
        use_system_role = True
        
        for attempt in range(retry_count + 1):
            try:
                # 部分模型不支持 system role，尝试两种消息格式
                if use_system_role:
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                else:
                    messages = [
                        {"role": "user", "content": f"{system_prompt}\n\n---\n\n{user_prompt}"}
                    ]
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=self.max_tokens
                )
                
                msg = response.choices[0].message
                content = msg.content or ""
                
                # 某些模型（如 DeepSeek R1）内容在 reasoning_content 中
                if not content and hasattr(msg, "reasoning_content"):
                    content = msg.reasoning_content or ""
                
                total_tokens = response.usage.total_tokens if response.usage else "N/A"
                meta = f"模型: {self.model} | 消耗tokens: {total_tokens}"
                
                # 检测空内容
                if not content or not content.strip():
                    if use_system_role and attempt == 0:
                        print("  [WARN] 模型返回空内容，尝试不使用 system role 重试...")
                        use_system_role = False
                        continue
                    return False, "", f"模型返回空内容（消耗tokens: {total_tokens}）。可能原因：1) 该模型不支持当前消息格式；2) 内容被安全过滤；3) 提示词过长被截断。"
                
                return True, content, meta
            
            except Exception as e:
                error_msg = str(e)
                
                # 处理 temperature 不兼容问题：自动调整为 1 并重试
                if "invalid temperature" in error_msg.lower() or "only 1 is allowed" in error_msg.lower():
                    if temperature != 1:
                        print(f"  [WARN] 当前模型不支持 temperature={temperature}，自动调整为 1 并重试...")
                        temperature = 1
                        continue  # 立即重试，不消耗 retry_count
                
                # 处理不支持 system role 的错误
                if "system" in error_msg.lower() and use_system_role:
                    print("  [WARN] 当前模型可能不支持 system role，尝试合并到 user message 重试...")
                    use_system_role = False
                    continue
                
                if attempt < retry_count:
                    wait_time = 2 ** attempt
                    print(f"  [WARN] 生成失败（{e}），{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    return False, "", f"生成失败: {error_msg}"
        
        # 兜底（理论上不会到达此处）
        return False, "", "生成失败: 未知错误"
    
    def generate_stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        """
        流式生成文案（新增）
        
        Yields:
            文本片段（逐字/逐词返回）
        """
        if not HAS_OPENAI:
            yield "[错误] 未安装openai包"
            return
        
        temperature = self.temperature
        use_system_role = True
        
        for attempt in range(3):
            try:
                if use_system_role:
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                else:
                    messages = [
                        {"role": "user", "content": f"{system_prompt}\n\n---\n\n{user_prompt}"}
                    ]
                
                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=self.max_tokens,
                    stream=True
                )
                
                for chunk in stream:
                    delta = chunk.choices[0].delta
                    text = delta.content or ""
                    if not text and hasattr(delta, "reasoning_content"):
                        text = delta.reasoning_content or ""
                    if text:
                        yield text
                
                return
            
            except Exception as e:
                err_str = str(e).lower()
                if "invalid temperature" in err_str and temperature != 1:
                    temperature = 1
                    continue
                if "system" in err_str and use_system_role:
                    use_system_role = False
                    continue
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    yield f"[错误] 流式生成失败: {e}"
                    return
    
    def save_generated(self, content: str, topic: str, meta: str,
                       output_dir: str = "data/generated") -> str:
        """保存生成的文案到文件"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_topic = re.sub(r'[^\w\u4e00-\u9fff]', '_', topic)[:30]
        filename = f"{timestamp}_{safe_topic}.md"
        filepath = output_path / filename
        
        header = f"""---
topic: {topic}
generated_at: {datetime.now().isoformat()}
meta: {meta}
---

"""
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(header + content)
        
        return str(filepath)
