from langgraph.graph import StateGraph, END
from graph.state import ChatState
from graph.nodes.entity_extractor import extract_entities
from graph.nodes.graph_retriever import graph_retrieve
from graph.nodes.vector_retriever import vector_retrieve
from graph.nodes.context_builder import build_context
from graph.nodes.generator import generate
from graph.nodes.suggestion_generator import generate_suggestions


def build_workflow() -> StateGraph:
    g = StateGraph(ChatState)

    g.add_node("extract_entities",     extract_entities)
    g.add_node("graph_retrieve",       graph_retrieve)
    g.add_node("vector_retrieve",      vector_retrieve)
    g.add_node("build_context",        build_context)
    g.add_node("generate",             generate)
    g.add_node("generate_suggestions", generate_suggestions)

    g.set_entry_point("extract_entities")
    g.add_edge("extract_entities",     "graph_retrieve")
    g.add_edge("extract_entities",     "vector_retrieve")   # parallel
    g.add_edge("graph_retrieve",       "build_context")
    g.add_edge("vector_retrieve",      "build_context")
    g.add_edge("build_context",        "generate")
    g.add_edge("generate",             "generate_suggestions")
    g.add_edge("generate_suggestions", END)

    return g.compile()


workflow = build_workflow()
