"""
LLM 工厂

统一创建 DeepSeek 模型实例，供资讯工作流的三个 LLM 节点
（翻译 / 摘要 / 审核）复用，避免在多处重复模型参数。
"""

import logging
from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


def create_llm(
    settings: Settings | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> ChatOpenAI:
    """
    创建 DeepSeek 模型实例

    Args:
        settings: 配置，缺省取全局配置
        temperature: 覆盖默认温度（审核等需要稳定输出的节点可调低）
        max_tokens: 覆盖默认输出上限（翻译整篇正文需要更大的值）

    Returns:
        ChatOpenAI 实例（指向 DeepSeek 兼容端点）
    """
    settings = settings or get_settings()

    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_api_url,
        temperature=settings.llm_temperature if temperature is None else temperature,
        max_tokens=settings.llm_max_tokens if max_tokens is None else max_tokens,
    )


@lru_cache(maxsize=8)
def _cached_llm(temperature: float, max_tokens: int) -> ChatOpenAI:
    """按温度与输出上限缓存模型实例"""
    return create_llm(temperature=temperature, max_tokens=max_tokens)


def get_llm(temperature: float | None = None, max_tokens: int | None = None) -> ChatOpenAI:
    """
    获取模型实例（带缓存）

    Args:
        temperature: 温度；缺省使用配置中的默认值
        max_tokens: 输出上限；缺省使用配置中的默认值
    """
    settings = get_settings()
    resolved_temperature = settings.llm_temperature if temperature is None else temperature
    resolved_max_tokens = settings.llm_max_tokens if max_tokens is None else max_tokens
    return _cached_llm(resolved_temperature, resolved_max_tokens)
