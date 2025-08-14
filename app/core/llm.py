from app.core.config import settings
from langchain_community.chat_models import ChatTongyi
from langchain.callbacks.tracers import ConsoleCallbackHandler
from app.llm.callback.capture_chat_messages import CaptureChatMessagesCallbackHandler

# 全局无状态模型
base_qwen_config = dict(
    model="qwen-flash",
    api_key=settings.DASHSCOPE_API_KEY,
    # 任何其它你需要传给 ChatTongyi 的参数比如 temperature, streaming 等
    callbacks=[ConsoleCallbackHandler()],
)


base_qwen_llm = ChatTongyi(**base_qwen_config)


def get_qwen_llm_with_capture():
    capture = CaptureChatMessagesCallbackHandler()
    cfg = base_qwen_config.copy()
    cfg["callbacks"] = cfg.get("callbacks", []) + [capture]
    return ChatTongyi(**cfg), capture
