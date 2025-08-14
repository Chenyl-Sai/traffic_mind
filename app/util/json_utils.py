from langchain_core.messages import BaseMessage
from pydantic import BaseModel
import json

def pydantic_to_dict(obj):
    if isinstance(obj, BaseModel):
        return obj.model_dump()  # Pydantic v2
        # return obj.dict()      # Pydantic v1
    elif isinstance(obj, dict):
        return {k: pydantic_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [pydantic_to_dict(v) for v in obj]
    elif isinstance(obj, BaseMessage):
        return {"LangChain Message" : obj.pretty_repr()}
    else:
        return obj  # 基本类型（str, int, float, bool）直接返回
