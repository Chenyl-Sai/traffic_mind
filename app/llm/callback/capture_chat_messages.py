from langchain.callbacks.base import BaseCallbackHandler

class CaptureChatMessagesCallbackHandler(BaseCallbackHandler):
    def __init__(self):
        self.captured = None  # 最终会是 List[BaseMessage]

    # chat models 会触发这个（messages: List[List[BaseMessage]]）
    async def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kwargs):
        # messages 是一个 batch 的列表，取第 0 个即可（单样本场景）
        if isinstance(messages, list) and len(messages) > 0:
            self.captured = messages[0]
        else:
            self.captured = messages

    # 作为向后兼容（某些 LLM 接口可能触发 on_llm_start，prompts 是 str list）
    async def on_llm_start(self, serialized, prompts, *, run_id, parent_run_id=None, **kwargs):
        # 如果 prompts 是字符串 list，可以把它们封装为 HumanMessage（按需）
        self.captured = prompts