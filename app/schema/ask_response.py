"""
问答接口SSE响应数据格式
"""
from typing import Any
from enum import Enum

from pydantic import BaseModel, Field


class SSEMessageTypeEnum(Enum):
    """SSE消息类型枚举"""
    # 拼接消息，客户端收到之后持续拼接
    APPEND = "append"
    # 最终消息，客户端收到之后停止拼接，同时关闭此次问答
    FINAL = "final"
    # 中断消息，客户端收到之后停止拼接，同时关闭此次问答，并根据中断返回的信息做后续补充(需人工/用户介入)
    INTERRUPT = "interrupt"
    # 系统提示消息
    SYSTEM = "system"
    # 异常消息
    ERROR = "error"
    # 过程消息，不显示给用户，用于记录过程信息
    HIDDEN = "hidden"


class SSEResponse(BaseModel):
    """
    SSE响应消息
    """
    message: str = Field(title="消息内容")
    interrupt_reason: str | None = Field(title="中断消息", description="当需要用户介入时需要提供说明", default=None)
    expect_fields: list[str] | None = Field(title="期望字段", description="当需要用户输入时需要提供字段名称",
                                            default=None)
    metadata: dict[str, Any] | None = Field(title="元数据", description="MessageId/Sender/Timestamp等信息",
                                            default=None)
