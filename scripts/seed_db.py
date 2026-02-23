"""Seed the database with sample data for development."""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Transcript
from src.db.session import async_session_factory


SAMPLE_TRANSCRIPTS = [
    {
        "meeting_id": "mtg_sample_001",
        "meeting_title": "Q1 Sprint Planning",
        "content": (
            "Alice: Welcome everyone. Let's plan the Q1 sprint.\n"
            "Bob: I can take the login bug. High priority, due Friday.\n"
            "Alice: Great. Let's schedule a review next Tuesday at 2pm.\n"
            "Charlie: I'll send a summary to stakeholders."
        ),
        "participants": ["alice@company.com", "bob@company.com", "charlie@company.com"],
        "status": "completed",
    },
    {
        "meeting_id": "mtg_sample_002",
        "meeting_title": "Customer Feedback Review",
        "content": (
            "Diana: We had 15 complaints about slow page loads.\n"
            "Evan: I'll investigate. Probably database queries.\n"
            "Diana: Create a high priority ticket. Fix before March 5th."
        ),
        "participants": ["diana@company.com", "evan@company.com"],
        "status": "pending",
    },
]


async def seed() -> None:
    async with async_session_factory() as session:
        for data in SAMPLE_TRANSCRIPTS:
            transcript = Transcript(
                id=uuid.uuid4(),
                meeting_id=data["meeting_id"],
                meeting_title=data["meeting_title"],
                content=data["content"],
                participants=data["participants"],
                status=data["status"],
            )
            session.add(transcript)

        await session.commit()
        print(f"Seeded {len(SAMPLE_TRANSCRIPTS)} transcripts")


if __name__ == "__main__":
    asyncio.run(seed())
