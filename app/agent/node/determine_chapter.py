"""
确定所属章节
"""
import logging

from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.graph import START, StateGraph, END
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from app.agent.constants import DetermineChapterNodes
from app.agent.state import HtsClassifyAgentState
from app.agent.constants import HtsAgents
from app.agent.util.exception_handler import safe_node
from app.core.llm import get_qwen_llm_with_capture
from app.llm.prompt.prompt_template import determine_chapter_template
from app.schema.llm.llm import ChapterDetermineResponse

logger = logging.getLogger(__name__)

def start_determine_chapter(state: HtsClassifyAgentState):
    return {"current_agent": HtsAgents.DETERMINE_CHAPTER.code}


@safe_node(logger=logger)
async def ask_llm_to_determine_chapter(state: HtsClassifyAgentState, config, store: BaseStore):
    chapter_documents = state.get("chapter_documents")
    parser = PydanticOutputParser(pydantic_object=ChapterDetermineResponse)
    format_instructions = parser.get_format_instructions()
    prompt = PromptTemplate(template=determine_chapter_template,
                            input_variables=["item", "chapter_list"],
                            partial_variables={"format_instructions": format_instructions})

    tongyi_chat, capture = get_qwen_llm_with_capture()

    chain = prompt | tongyi_chat

    output = await chain.ainvoke({"item": state.get("rewritten_item"),
                                  "chapter_list": chapter_documents})

    return {"messages": [*capture.captured, output]}


@safe_node(logger=logger)
def determine_chapter(state: HtsClassifyAgentState, config, store: BaseStore):
    last_message = state["messages"][-1]
    parser = PydanticOutputParser(pydantic_object=ChapterDetermineResponse)
    determine_chapter_response = parser.parse(last_message.content)

    final_alternative_chapters = [
        chapter for chapter in determine_chapter_response.alternative_chapters
        # if chapter.confidence_score > 5
    ]

    return {
        "main_chapter": determine_chapter_response.main_chapter,
        "alternative_chapters": final_alternative_chapters
    }

async def save_exact_match_cache(state: HtsClassifyAgentState, config, store: BaseStore):
    """
    保存精确匹配的缓存
        将结构化的重写的商品进行进行拼接之后hash作为key，存储确定的章节结果
    """


async def save_layered_chapter_cache(state: HtsClassifyAgentState, config, store: BaseStore):
    """
    保存分层的章节缓存
        存储结构化的章节信息的embedding向量信息，然后根据语义相似度获取之前确定的章节结果
    """



def build_determine_chapter_graph() -> CompiledStateGraph:
    """
    构建确定所属章节的图
    """
    graph_builder = StateGraph(HtsClassifyAgentState)
    graph_builder.add_node(DetermineChapterNodes.ENTER_DETERMINE_CHAPTER, start_determine_chapter)
    graph_builder.add_node(DetermineChapterNodes.ASK_LLM_TO_DETERMINE_CHAPTER, ask_llm_to_determine_chapter)
    graph_builder.add_node(DetermineChapterNodes.DETERMINE_CHAPTER, determine_chapter)
    graph_builder.add_edge(START, DetermineChapterNodes.ENTER_DETERMINE_CHAPTER)
    graph_builder.add_edge(DetermineChapterNodes.ENTER_DETERMINE_CHAPTER,
                           DetermineChapterNodes.ASK_LLM_TO_DETERMINE_CHAPTER)
    graph_builder.add_conditional_edges(DetermineChapterNodes.ASK_LLM_TO_DETERMINE_CHAPTER,
                                        lambda state: "error" if state.get("unexpected_error") else "normal",
                                        {"error": END, "normal": DetermineChapterNodes.DETERMINE_CHAPTER})
    return graph_builder.compile()
