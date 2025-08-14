"""
扩展hstitle信息
"""
from langchain_community.chat_models import ChatTongyi
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from app.core.config import settings
from app.schema.llm.llm import ChapterExtends
from app.llm.prompt.prompt_template import expend_chapter_template


async def get_chapter_extends(title: str) -> ChapterExtends:
    tongyi_chat = ChatTongyi(model="qwen-max-latest", api_key=settings.DASHSCOPE_API_KEY)
    pydantic_parser = PydanticOutputParser(pydantic_object=ChapterExtends)
    format_instructions = pydantic_parser.get_format_instructions()
    prompt = PromptTemplate(
        template=expend_chapter_template,
        input_variables=["title"],
        partial_variables={"format_instructions": format_instructions}
    )
    chain = prompt | tongyi_chat | pydantic_parser
    return await chain.ainvoke({"title": title})


