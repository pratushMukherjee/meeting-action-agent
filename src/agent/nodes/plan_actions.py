"""Plan execution order for extracted action items."""

from __future__ import annotations

import json
from pathlib import Path

from langchain_openai import ChatOpenAI

from src.agent.state import ActionItem, MeetingAgentState, PlannedTask
from src.core.config import settings
from src.core.logging import get_logger
from src.core.metrics import LLM_LATENCY, LLM_TOKENS_TOTAL

logger = get_logger(__name__)

PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "plan_actions.txt"


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _build_default_plan(items: list[ActionItem]) -> list[PlannedTask]:
    """Build a deterministic default plan when LLM planning is unnecessary or fails.

    Ordering: Jira tickets first (order 0), then calendar events (order 1, parallel),
    then email summaries last (order 2, depends on all prior).
    """
    plan: list[PlannedTask] = []
    order_counter = 0

    jira_orders: list[int] = []
    for item in items:
        if item.type == "jira_ticket":
            plan.append(PlannedTask(
                action_item=item,
                order=order_counter,
                can_parallel=True,
            ))
            jira_orders.append(order_counter)
            order_counter += 1

    calendar_start = order_counter
    for item in items:
        if item.type == "calendar_event":
            plan.append(PlannedTask(
                action_item=item,
                order=order_counter,
                can_parallel=True,
            ))
            order_counter += 1

    for item in items:
        if item.type == "email_summary":
            plan.append(PlannedTask(
                action_item=item,
                order=order_counter,
                depends_on=list(range(calendar_start)),  # Depends on jira tickets
                can_parallel=False,
            ))
            order_counter += 1

    return plan


async def plan_actions(state: MeetingAgentState) -> dict:
    """LangGraph node: create an ordered execution plan for action items.

    Takes parsed action items and determines execution order, dependencies,
    and parallelization opportunities.
    """
    parsed_items = state.get("parsed_items", [])

    if not parsed_items:
        logger.info("no_action_items_to_plan", transcript_id=state["transcript_id"])
        return {
            "execution_plan": [],
            "current_step": "plan_actions",
        }

    # For small sets of items, use deterministic planning
    if len(parsed_items) <= 5:
        plan = _build_default_plan(parsed_items)
        logger.info(
            "plan_created_deterministic",
            transcript_id=state["transcript_id"],
            planned_tasks=len(plan),
        )
        return {
            "execution_plan": plan,
            "current_step": "plan_actions",
        }

    # For complex sets, use LLM-based planning
    prompt_template = _load_prompt()
    items_json = json.dumps(
        [item.model_dump() for item in parsed_items],
        indent=2,
    )
    prompt = prompt_template.format(action_items=items_json)

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.0,
    )

    with LLM_LATENCY.labels(model=settings.openai_model).time():
        response = await llm.ainvoke(prompt)

    if response.usage_metadata:
        LLM_TOKENS_TOTAL.labels(model=settings.openai_model, type="input").inc(
            response.usage_metadata.get("input_tokens", 0)
        )
        LLM_TOKENS_TOTAL.labels(model=settings.openai_model, type="output").inc(
            response.usage_metadata.get("output_tokens", 0)
        )

    raw_content = response.content
    raw_text = str(raw_content).strip()

    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw_text = "\n".join(lines)

    try:
        plan_data = json.loads(raw_text)
        plan = [PlannedTask.model_validate(task) for task in plan_data]
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("llm_plan_parse_failed, using_default", error=str(e))
        plan = _build_default_plan(parsed_items)

    logger.info(
        "plan_created",
        transcript_id=state["transcript_id"],
        planned_tasks=len(plan),
    )

    return {
        "execution_plan": plan,
        "current_step": "plan_actions",
    }
