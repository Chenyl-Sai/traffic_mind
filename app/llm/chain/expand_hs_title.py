"""
扩展hstitle信息
"""
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from app.schema.llm.llm import ChapterExtends, HeadingExtends
from app.llm.prompt.prompt_template import expend_chapter_template, expend_heading_template
from app.core.llm import qwen_max_llm


async def get_chapter_extends(title: str) -> ChapterExtends:
    pydantic_parser = PydanticOutputParser(pydantic_object=ChapterExtends)
    format_instructions = pydantic_parser.get_format_instructions()
    prompt = PromptTemplate(
        template=expend_chapter_template,
        input_variables=["title"],
        partial_variables={"format_instructions": format_instructions}
    )
    chain = prompt | qwen_max_llm | pydantic_parser
    return await chain.ainvoke({"title": title})


async def get_heading_extends(chapter_title: str, heading_title: str) -> HeadingExtends:
    pydantic_parser = PydanticOutputParser(pydantic_object=HeadingExtends)
    format_instructions = pydantic_parser.get_format_instructions()
    prompt = PromptTemplate(
        template=expend_heading_template,
        input_variables=["chapter_title", "heading_title"],
        partial_variables={"format_instructions": format_instructions}
    )
    chain = prompt | qwen_max_llm | pydantic_parser
    return await chain.ainvoke({"chapter_title": chapter_title, "heading_title": heading_title})
