"""
测试用假模型

LangChain 自带的 FakeListChatModel 在 langchain-core 1.x 中未实现 bind_tools，
而 create_agent 会调用它，因此这里提供一个最小可用实现：

- 支持 bind_tools（原样返回自身）
- 支持逐字符流式输出，用于验证流式链路
"""

from typing import Any, Iterator, Sequence

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult


class FakeToolChatModel(BaseChatModel):
    """支持工具绑定与逐字符流式的假聊天模型"""

    response: str = "这是一段测试回答"

    @property
    def _llm_type(self) -> str:
        return "fake-tool-chat-model"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "FakeToolChatModel":
        """接受工具绑定但不改变行为（不发起工具调用）"""
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        message = AIMessage(content=self.response)
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """逐字符产出，模拟真实的 token 级流式输出"""
        for char in self.response:
            chunk = ChatGenerationChunk(message=AIMessageChunk(content=char))
            if run_manager:
                run_manager.on_llm_new_token(char, chunk=chunk)
            yield chunk
