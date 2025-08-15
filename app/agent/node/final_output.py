"""
生成最终输出
"""
import logging

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.graph import START, StateGraph
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.agent.constants import GenerateFinalOutputNodes
from app.agent.state import HtsClassifyAgentState
from app.agent.constants import HtsAgents
from app.agent.util.exception_handler import safe_raise_exception_node
from app.core.llm import get_qwen_llm_with_capture
from app.llm.prompt.prompt_template import generate_final_output_template
from app.schema.llm.llm import GenerateFinalOutputResponse

logger = logging.getLogger(__name__)

def start_generate_final_output(state: HtsClassifyAgentState):
    return {"current_agent": HtsAgents.GENERATE_FINAL_OUTPUT.code}


@safe_raise_exception_node(logger=logger)
async def ask_llm_to_generate_final_output(state: HtsClassifyAgentState, config, store: BaseStore):
    messages = state["messages"]
    parser = PydanticOutputParser(pydantic_object=GenerateFinalOutputResponse)
    format_instructions = parser.get_format_instructions()

    message = (ChatPromptTemplate.from_template(template=generate_final_output_template)
               .format(format_instructions=format_instructions))

    prompt = ChatPromptTemplate.from_messages(messages + [HumanMessage(content=message)])

    tongyi_chat, capture = get_qwen_llm_with_capture()

    chain = prompt | tongyi_chat

    output = await chain.ainvoke({})

    return {"messages": [*capture.captured, output], "final_output": parser.parse(output.content).model_dump()}


async def save_final_output(state: HtsClassifyAgentState):
    document = {
        "origin_item_name": state["item"],
        "origin_item_ch_name": state["item"],
        "origin_item_ch_name_vector": state["item"],
        "origin_item_en_name": state["item"],
        "origin_item_en_name_vector": state["item"],
        "rewrite_result": state["item"],
        "user_id": state["item"],
        "thread_id": state["item"],
    }


def build_generate_final_output_graph() -> CompiledStateGraph:
    """
    生成最终输出
    """
    graph_builder = StateGraph(HtsClassifyAgentState)

    graph_builder.add_node(GenerateFinalOutputNodes.ENTER_GENERATE_FINAL_OUTPUT,
                           start_generate_final_output)
    graph_builder.add_node(GenerateFinalOutputNodes.ASK_LLM_TO_GENERATE_FINAL_OUTPUT,
                           ask_llm_to_generate_final_output)
    graph_builder.add_edge(START, GenerateFinalOutputNodes.ENTER_GENERATE_FINAL_OUTPUT)
    graph_builder.add_edge(GenerateFinalOutputNodes.ENTER_GENERATE_FINAL_OUTPUT,
                           GenerateFinalOutputNodes.ASK_LLM_TO_GENERATE_FINAL_OUTPUT)
    return graph_builder.compile()
