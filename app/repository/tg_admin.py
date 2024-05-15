from sqlalchemy import update
from sqlalchemy.future import select

from app.db.models import TgAdmin
from app.db.session import db_session


class TgAdminRepository:
    @classmethod
    async def list(cls, **kwargs):
        async with db_session() as session:
            query = select(TgAdmin)

            for key, value in kwargs.items():
                if hasattr(TgAdmin, key):
                    query = query.filter(getattr(TgAdmin, key) == value)

            result = await session.execute(query)
            return result.scalars().unique().all()

    @staticmethod
    async def get(telegram_id: int):
        async with db_session() as db:
            result = await db.execute(select(TgAdmin).where(TgAdmin.telegram_id == telegram_id))
            return result.scalars().first() is not None

    @staticmethod
    async def update(telegram_id: int, **kwargs):
        async with db_session() as session:
            query = update(TgAdmin).where(TgAdmin.telegram_id == telegram_id).values(**kwargs)
            await session.execute(query)
            await session.commit()
