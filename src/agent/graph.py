"""LangGraph StateGraph definition for the Meeting Action Agent.

This is the central file that defines the agent's workflow topology,
registers all nodes, and configures edge routing.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.agent.edges.routing import (
    route_after_approval,
    route_after_parsing,
    should_continue_or_end,
)
from src.agent.nodes.human_approval import human_approval
from src.agent.nodes.parse_transcript import parse_transcript
from src.agent.nodes.plan_actions import plan_actions
from src.agent.nodes.synthesize import synthesize
from src.agent.state import MeetingAgentState
from src.agent.workers.calendar_worker import calendar_worker
from src.agent.workers.email_worker import email_worker
from src.agent.workers.jira_worker import jira_worker


def build_graph(checkpointer=None) -> StateGraph:
    """Build and compile the Meeting Action Agent graph.

    Args:
        checkpointer: LangGraph checkpointer for state persistence.
            Defaults to MemorySaver for development.
            Use AsyncPostgresSaver or AsyncRedisSaver for production.

    Returns:
        Compiled StateGraph ready for invocation.
    """
    if checkpointer is None:
        checkpointer = MemorySaver()

    # Define the graph
    graph = StateGraph(MeetingAgentState)

    # --- Register Nodes ---
    graph.add_node("parse_transcript", parse_transcript)
    graph.add_node("plan_actions", plan_actions)
    graph.add_node("human_approval", human_approval)
    graph.add_node("jira_worker", jira_worker)
    graph.add_node("email_worker", email_worker)
    graph.add_node("calendar_worker", calendar_worker)
    graph.add_node("synthesize", synthesize)

    # --- Define Edges ---

    # Entry point: start with transcript parsing
    graph.set_entry_point("parse_transcript")

    # After parsing: route to planning or skip to synthesize if no items
    graph.add_conditional_edges(
        "parse_transcript",
        route_after_parsing,
        {
            "plan_actions": "plan_actions",
            "synthesize": "synthesize",
        },
    )

    # After planning: always go to human approval
    graph.add_edge("plan_actions", "human_approval")

    # After approval: fan out to workers or skip to synthesize
    graph.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "synthesize": "synthesize",
            "jira_worker": "jira_worker",
            "email_worker": "email_worker",
            "calendar_worker": "calendar_worker",
        },
    )

    # After each worker: route to synthesize
    graph.add_conditional_edges("jira_worker", should_continue_or_end, {"synthesize": "synthesize"})
    graph.add_conditional_edges("email_worker", should_continue_or_end, {"synthesize": "synthesize"})
    graph.add_conditional_edges("calendar_worker", should_continue_or_end, {"synthesize": "synthesize"})

    # Synthesize is the terminal node
    graph.add_edge("synthesize", END)

    # Compile with checkpointer
    return graph.compile(checkpointer=checkpointer)


# Default graph instance for development/testing
app = build_graph()
