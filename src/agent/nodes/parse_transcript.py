"""Parse meeting transcript to extract structured action items."""

from __future__ import annotations

import json
from pathlib import Path

from langchain_openai import ChatOpenAI

from src.agent.state import ActionItem, MeetingAgentState
from src.core.config import settings
from src.core.logging import get_logger
from src.core.metrics import LLM_LATENCY, LLM_TOKENS_TOTAL

logger = get_logger(__name__)

PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "parse_transcript.txt"


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


async def parse_transcript(state: MeetingAgentState) -> dict:
    """LangGraph node: parse transcript and extract action items.

    Reads the raw transcript from state, calls the LLM with a structured
    extraction prompt, and returns a list of ActionItem objects.
    """
    logger.info(
        "parsing_transcript",
        transcript_id=state["transcript_id"],
        transcript_length=len(state["transcript"]),
    )

    prompt_template = _load_prompt()
    prompt = (
        prompt_template
        .replace("{transcript}", state["transcript"])
        .replace("{participants}", ", ".join(state.get("participants", [])))
        .replace("{meeting_date}", state.get("meeting_metadata", {}).get("date", "unknown"))
    )

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.1,
    )

    with LLM_LATENCY.labels(model=settings.openai_model).time():
        response = await llm.ainvoke(prompt)

    # Track token usage
    if response.usage_metadata:
        LLM_TOKENS_TOTAL.labels(
            model=settings.openai_model, type="input"
        ).inc(response.usage_metadata.get("input_tokens", 0))
        LLM_TOKENS_TOTAL.labels(
            model=settings.openai_model, type="output"
        ).inc(response.usage_metadata.get("output_tokens", 0))

    # Parse LLM response into ActionItem objects
    raw_content = response.content
    if isinstance(raw_content, list):
        raw_content = raw_content[0] if raw_content else "[]"
    raw_text = str(raw_content).strip()

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        lines = lines[1:]  # Remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]  # Remove closing fence
        raw_text = "\n".join(lines)

    try:
        items_data = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.error("failed_to_parse_llm_response", raw_text=raw_text[:500])
        return {"parsed_items": [], "current_step": "parse_transcript"}

    parsed_items = []
    for item_data in items_data:
        try:
            item = ActionItem.model_validate(item_data)
            parsed_items.append(item)
        except Exception as e:
            logger.warning("skipping_invalid_action_item", error=str(e), data=item_data)

    logger.info(
        "transcript_parsed",
        transcript_id=state["transcript_id"],
        action_items_found=len(parsed_items),
        types=[item.type for item in parsed_items],
    )

    return {
        "parsed_items": parsed_items,
        "current_step": "parse_transcript",
    }
