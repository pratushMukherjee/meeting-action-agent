"""Human-in-the-loop approval gate for execution plans."""

from __future__ import annotations

from langgraph.types import interrupt

from src.agent.state import MeetingAgentState
from src.core.logging import get_logger

logger = get_logger(__name__)


async def human_approval(state: MeetingAgentState) -> dict:
    """LangGraph node: pause execution and request human approval.

    Presents the execution plan to the user via LangGraph's interrupt()
    mechanism. The graph pauses here until the user approves, edits,
    or rejects the plan via the API.
    """
    execution_plan = state.get("execution_plan", [])

    if not execution_plan:
        logger.info("no_plan_to_approve", transcript_id=state["transcript_id"])
        return {"human_approved": True, "current_step": "human_approval"}

    # Build a human-readable summary of the plan
    plan_summary = []
    for task in execution_plan:
        item = task.action_item
        plan_summary.append({
            "order": task.order,
            "type": item.type,
            "title": item.title,
            "description": item.description,
            "assignee": item.assignee,
            "priority": item.priority,
            "confidence": item.confidence,
            "can_parallel": task.can_parallel,
            "depends_on": task.depends_on,
        })

    logger.info(
        "requesting_human_approval",
        transcript_id=state["transcript_id"],
        planned_actions=len(plan_summary),
    )

    # Interrupt execution and wait for human input.
    # The API layer resumes the graph with Command(resume={"approved": True/False})
    approval = interrupt({
        "message": "Please review the execution plan before proceeding.",
        "plan": plan_summary,
        "total_actions": len(plan_summary),
        "action_types": list({task.action_item.type for task in execution_plan}),
    })

    approved = approval.get("approved", False) if isinstance(approval, dict) else bool(approval)

    if approved:
        logger.info("plan_approved", transcript_id=state["transcript_id"])
        # Allow plan edits if provided
        edited_plan = approval.get("edited_plan") if isinstance(approval, dict) else None
        if edited_plan:
            return {
                "execution_plan": edited_plan,
                "human_approved": True,
                "current_step": "human_approval",
            }
        return {"human_approved": True, "current_step": "human_approval"}
    else:
        logger.info("plan_rejected", transcript_id=state["transcript_id"])
        return {
            "human_approved": False,
            "execution_plan": [],
            "current_step": "human_approval",
        }
