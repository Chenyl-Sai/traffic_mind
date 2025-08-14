"""
确定所属税率线
"""
import logging

from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.graph import START, StateGraph, END
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from app.agent.constants import DetermineRateLineNodes
from app.agent.state import HtsClassifyAgentState
from app.agent.constants import HtsAgents
from app.agent.util.exception_handler import safe_node
from app.core.llm import get_qwen_llm_with_capture
from app.llm.prompt.prompt_template import determine_rate_line_template
from app.schema.llm.llm import RateLineDetermineResponse

logger = logging.getLogger(__name__)


def start_determine_rate_line(state: HtsClassifyAgentState):
    return {"current_agent": HtsAgents.DETERMINE_RATE_LINE.code}


@safe_node(logger=logger)
async def ask_llm_to_determine_rate_line(state: HtsClassifyAgentState, config, store: BaseStore):
    rate_line_documents = state.get("rate_line_documents")
    parser = PydanticOutputParser(pydantic_object=RateLineDetermineResponse)
    format_instructions = parser.get_format_instructions()
    prompt = PromptTemplate(template=determine_rate_line_template,
                            input_variables=["item", "rate_line_list"],
                            partial_variables={"format_instructions": format_instructions})

    tongyi_chat, capture = get_qwen_llm_with_capture()

    chain = prompt | tongyi_chat

    output = await chain.ainvoke({"item": state.get("rewritten_item"),
                                  "rate_line_list": rate_line_documents})

    return {"messages": [*capture.captured, output]}


@safe_node(logger=logger)
def determine_rate_line(state: HtsClassifyAgentState, config, store: BaseStore):
    last_message = state["messages"][-1]
    parser = PydanticOutputParser(pydantic_object=RateLineDetermineResponse)
    determine_subheading_response = parser.parse(last_message.content)
    return {
        "main_rate_line": determine_subheading_response,
    }


def build_determine_subheading_graph() -> CompiledStateGraph:
    """
    构建确定所属税率线的图
    """
    graph_builder = StateGraph(HtsClassifyAgentState)
    graph_builder.add_node(DetermineRateLineNodes.ENTER_DETERMINE_RATE_LINE, start_determine_rate_line)
    graph_builder.add_node(DetermineRateLineNodes.ASK_LLM_TO_DETERMINE_RATE_LINE, ask_llm_to_determine_rate_line)
    graph_builder.add_node(DetermineRateLineNodes.DETERMINE_RATE_LINE, determine_rate_line)
    graph_builder.add_edge(START, DetermineRateLineNodes.ENTER_DETERMINE_RATE_LINE)
    graph_builder.add_edge(DetermineRateLineNodes.ENTER_DETERMINE_RATE_LINE,
                           DetermineRateLineNodes.ASK_LLM_TO_DETERMINE_RATE_LINE)
    graph_builder.add_conditional_edges(DetermineRateLineNodes.ASK_LLM_TO_DETERMINE_RATE_LINE,
                                        lambda state: "error" if state.get("unexpected_error") else "normal",
                                        {"error": END, "normal": DetermineRateLineNodes.DETERMINE_RATE_LINE})
    return graph_builder.compile()
