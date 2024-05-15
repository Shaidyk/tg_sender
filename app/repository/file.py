from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import File
from app.db.session import db_session


class TemplateRepository:
    @classmethod
    async def list(cls):
        async with db_session() as session:
            result = await session.execute(select(File))
            return result.scalars().all()

    @classmethod
    async def get(cls, template_id: int):
        async with db_session() as session:
            result = await session.execute(select(File).filter(File.template_id == template_id))
            return result.scalars().all()

    @classmethod
    async def create(cls, update_data: dict):
        async with db_session() as session:
            file = File(**update_data)
            session.add(file)
            await session.commit()
            await session.refresh(file)
            return file
