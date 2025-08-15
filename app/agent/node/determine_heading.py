"""
确定所属类目
"""
import logging

from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.graph import START, StateGraph, END
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from app.agent.constants import DetermineHeadingNodes
from app.agent.state import HtsClassifyAgentState
from app.agent.constants import HtsAgents
from app.agent.util.exception_handler import safe_raise_exception_node
from app.core.llm import get_qwen_llm_with_capture
from app.llm.prompt.prompt_template import determine_heading_template
from app.schema.llm.llm import HeadingDetermineResponse

logger = logging.getLogger(__name__)

def start_determine_heading(state: HtsClassifyAgentState):
    return {"current_agent": HtsAgents.DETERMINE_HEADING.code}


@safe_raise_exception_node(logger=logger)
async def ask_llm_to_determine_heading(state: HtsClassifyAgentState, config, store: BaseStore):
    heading_documents = state.get("heading_documents")
    parser = PydanticOutputParser(pydantic_object=HeadingDetermineResponse)
    format_instructions = parser.get_format_instructions()
    prompt = PromptTemplate(template=determine_heading_template,
                            input_variables=["item", "heading_list"],
                            partial_variables={"format_instructions": format_instructions})

    tongyi_chat, capture = get_qwen_llm_with_capture()

    chain = prompt | tongyi_chat

    output = await chain.ainvoke({"item": state.get("rewritten_item"),
                                  "heading_list": heading_documents})

    return {"messages": [*capture.captured, output]}


@safe_raise_exception_node(logger=logger)
def determine_heading(state: HtsClassifyAgentState, config, store: BaseStore):
    last_message = state["messages"][-1]
    parser = PydanticOutputParser(pydantic_object=HeadingDetermineResponse)
    determine_heading_response = parser.parse(last_message.content)
    final_alternative_headings = []
    if determine_heading_response.alternative_headings:
        final_alternative_headings = [
            heading for heading in determine_heading_response.alternative_headings
            # if heading.confidence_score > 5
        ]

    return {
        "main_heading": determine_heading_response.main_heading,
        "alternative_headings": final_alternative_headings
    }


def build_determine_heading_graph() -> CompiledStateGraph:
    """
    构建确定所属类目的图
    """
    graph_builder = StateGraph(HtsClassifyAgentState)
    graph_builder.add_node(DetermineHeadingNodes.ENTER_DETERMINE_HEADING, start_determine_heading)
    graph_builder.add_node(DetermineHeadingNodes.ASK_LLM_TO_DETERMINE_HEADING, ask_llm_to_determine_heading)
    graph_builder.add_node(DetermineHeadingNodes.DETERMINE_HEADING, determine_heading)
    graph_builder.add_edge(START, DetermineHeadingNodes.ENTER_DETERMINE_HEADING)
    graph_builder.add_edge(DetermineHeadingNodes.ENTER_DETERMINE_HEADING,
                           DetermineHeadingNodes.ASK_LLM_TO_DETERMINE_HEADING)
    graph_builder.add_conditional_edges(DetermineHeadingNodes.ASK_LLM_TO_DETERMINE_HEADING,
                                        lambda state: "error" if state.get("unexpected_error") else "normal",
                                        {"error": END, "normal": DetermineHeadingNodes.DETERMINE_HEADING})
    return graph_builder.compile()
