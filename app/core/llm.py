from app.core.config import settings
from langchain_community.chat_models import ChatTongyi
from langchain.callbacks.tracers import ConsoleCallbackHandler
from langchain_deepseek.chat_models import ChatDeepSeek
from app.llm.callback.capture_chat_messages import CaptureChatMessagesCallbackHandler

############################# qwen model ######################################
# 全局无状态模型
base_qwen_config = dict(
    model="qwen-flash",
    api_key=settings.DASHSCOPE_API_KEY,
    # 任何其它你需要传给 ChatTongyi 的参数比如 temperature, streaming 等
    callbacks=[ConsoleCallbackHandler()],
)

base_qwen_llm = ChatTongyi(**base_qwen_config)

qwen_turbo_llm = ChatTongyi(
    model="qwen-turbo",
    api_key=settings.DASHSCOPE_API_KEY,
    callbacks=[ConsoleCallbackHandler()],)

qwen_plus_llm = ChatTongyi(
    model="qwen-plus",
    api_key=settings.DASHSCOPE_API_KEY,
    callbacks=[ConsoleCallbackHandler()],
)

qwen_max_llm = ChatTongyi(
    model="qwen-max-latest",
    api_key=settings.DASHSCOPE_API_KEY,
    callbacks=[ConsoleCallbackHandler()],
)

def get_qwen_llm_with_capture():
    capture = CaptureChatMessagesCallbackHandler()
    cfg = base_qwen_config.copy()
    cfg["callbacks"] = cfg.get("callbacks", []) + [capture]
    return ChatTongyi(**cfg), capture




############################# deepseek model ######################################
deep_seek_llm = ChatDeepSeek(
    model="deepseek-chat",
    api_key=settings.DEEPSEEK_API_KEY,
    callbacks=[ConsoleCallbackHandler()],
)

