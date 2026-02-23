import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ActionRecord, AuditLog, Transcript


class TranscriptRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, content: str, **kwargs) -> Transcript:
        transcript = Transcript(content=content, **kwargs)
        self.session.add(transcript)
        await self.session.flush()
        return transcript

    async def get_by_id(self, transcript_id: uuid.UUID) -> Transcript | None:
        result = await self.session.execute(
            select(Transcript).where(Transcript.id == transcript_id)
        )
        return result.scalar_one_or_none()

    async def update_status(self, transcript_id: uuid.UUID, status: str) -> None:
        await self.session.execute(
            update(Transcript)
            .where(Transcript.id == transcript_id)
            .values(status=status)
        )


class ActionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, transcript_id: uuid.UUID, **kwargs) -> ActionRecord:
        action = ActionRecord(transcript_id=transcript_id, **kwargs)
        self.session.add(action)
        await self.session.flush()
        return action

    async def get_by_transcript(self, transcript_id: uuid.UUID) -> list[ActionRecord]:
        result = await self.session.execute(
            select(ActionRecord)
            .where(ActionRecord.transcript_id == transcript_id)
            .order_by(ActionRecord.created_at)
        )
        return list(result.scalars().all())

    async def update_status(
        self, action_id: uuid.UUID, status: str, **kwargs
    ) -> None:
        await self.session.execute(
            update(ActionRecord)
            .where(ActionRecord.id == action_id)
            .values(status=status, **kwargs)
        )


class AuditRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(self, transcript_id: uuid.UUID, tool_name: str, action: str, **kwargs) -> None:
        entry = AuditLog(
            transcript_id=transcript_id,
            tool_name=tool_name,
            action=action,
            **kwargs,
        )
        self.session.add(entry)
        await self.session.flush()
