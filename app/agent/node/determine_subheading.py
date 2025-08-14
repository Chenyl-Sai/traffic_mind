"""
确定所属子目
"""
import logging

from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.graph import START, StateGraph, END
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from app.agent.constants import DetermineSubheadingNodes
from app.agent.state import HtsClassifyAgentState
from app.agent.constants import HtsAgents
from app.agent.util.exception_handler import safe_node
from app.core.llm import get_qwen_llm_with_capture
from app.llm.prompt.prompt_template import determine_subheading_template
from app.schema.llm.llm import SubheadingDetermineResponse

logger = logging.getLogger(__name__)


def start_determine_subheading(state: HtsClassifyAgentState):
    return {"current_agent": HtsAgents.DETERMINE_SUBHEADING.code}


@safe_node(logger=logger)
async def ask_llm_to_determine_subheading(state: HtsClassifyAgentState, config, store: BaseStore):
    subheading_documents = state.get("subheading_documents")
    parser = PydanticOutputParser(pydantic_object=SubheadingDetermineResponse)
    format_instructions = parser.get_format_instructions()
    prompt = PromptTemplate(template=determine_subheading_template,
                            input_variables=["item", "subheading_list"],
                            partial_variables={"format_instructions": format_instructions})

    tongyi_chat, capture = get_qwen_llm_with_capture()

    chain = prompt | tongyi_chat

    output = await chain.ainvoke({"item": state.get("rewritten_item"),
                                  "subheading_list": subheading_documents})

    return {"messages": [*capture.captured, output]}


@safe_node(logger=logger)
def determine_subheading(state: HtsClassifyAgentState, config, store: BaseStore):
    last_message = state["messages"][-1]
    parser = PydanticOutputParser(pydantic_object=SubheadingDetermineResponse)
    determine_subheading_response = parser.parse(last_message.content)
    final_alternative_subheadings = []
    if determine_subheading_response.alternative_subheadings:
        final_alternative_subheadings = [
            heading for heading in determine_subheading_response.alternative_subheadings
            # if heading.confidence_score > 5
        ]

    return {
        "main_subheading": determine_subheading_response.main_subheading,
        "alternative_subheadings": final_alternative_subheadings
    }


def build_determine_subheading_graph() -> CompiledStateGraph:
    """
    构建确定所属子目的图
    """
    graph_builder = StateGraph(HtsClassifyAgentState)
    graph_builder.add_node(DetermineSubheadingNodes.ENTER_DETERMINE_SUBHEADING, start_determine_subheading)
    graph_builder.add_node(DetermineSubheadingNodes.ASK_LLM_TO_DETERMINE_SUBHEADING, ask_llm_to_determine_subheading)
    graph_builder.add_node(DetermineSubheadingNodes.DETERMINE_SUBHEADING, determine_subheading)
    graph_builder.add_edge(START, DetermineSubheadingNodes.ENTER_DETERMINE_SUBHEADING)
    graph_builder.add_edge(DetermineSubheadingNodes.ENTER_DETERMINE_SUBHEADING,
                           DetermineSubheadingNodes.ASK_LLM_TO_DETERMINE_SUBHEADING)
    graph_builder.add_conditional_edges(DetermineSubheadingNodes.ASK_LLM_TO_DETERMINE_SUBHEADING,
                                        lambda state: "error" if state.get("unexpected_error") else "normal",
                                        {"error": END, "normal": DetermineSubheadingNodes.DETERMINE_SUBHEADING})
    return graph_builder.compile()
