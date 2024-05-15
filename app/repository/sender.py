import asyncio
from datetime import datetime, timedelta
from typing import List

from sqlalchemy import and_, or_, nullsfirst, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import Sender
from app.db.session import db_session


class SenderRepository:
    @classmethod
    async def list(cls, **kwargs):
        async with db_session() as session:
            query = select(Sender)
            for key, value in kwargs.items():
                if hasattr(Sender, key):
                    query = query.filter(getattr(Sender, key) == value)

            result = await session.execute(query)
            return result.scalars().unique().all()

    @classmethod
    async def get(cls, phone: str):
        async with db_session() as session:
            result = await session.execute(select(Sender).filter(Sender.phone == phone))
            return result.scalars().first()

    @classmethod
    async def get_by_id(cls, sender_id: int):
        async with db_session() as session:
            result = await session.execute(select(Sender).filter(Sender.id == sender_id))
            return result.scalars().first()

    @classmethod
    async def create(cls, update_data: dict):
        async with db_session() as session:
            sender = Sender(**update_data)
            session.add(sender)
            await session.commit()
            await session.refresh(sender)
            return sender

    @classmethod
    async def update(cls, sender_id: int, **kwargs):
        async with db_session() as session:
            result = await session.execute(select(Sender).filter(Sender.id == sender_id))
            sender = result.scalar()
            if sender is None:
                raise ValueError("Sender not found")

            for key, value in kwargs.items():
                if hasattr(Sender, key):
                    setattr(sender, key, value)

            await session.commit()
            return sender

    @classmethod
    async def create_bulk(cls, items: List[dict]):
        """
        Массовое создание записей в базе данных.
        :param items: список словарей с данными для вставки.
        """
        async with db_session() as session, session.begin():
            stmt = insert(Sender).values(items).returning(Sender)
            result = await session.execute(stmt)
            created_senders = result.scalars().all()
            for sender in created_senders:
                print(f"Created sender with ID: {sender.id}")

    @classmethod
    async def get_available_sender(cls):
        async with db_session() as session:
            three_minutes_ago = datetime.now() - timedelta(minutes=3)
            # Попытка найти доступного отправителя с учетом приоритета null значений
            query = select(Sender).where(
                and_(
                    or_(
                        Sender.last_message_datetime == None,
                        Sender.last_message_datetime < three_minutes_ago
                    ),
                    Sender.is_blocked == False
                )
            ).order_by(
                func.coalesce(Sender.last_message_datetime, datetime.min),
                Sender.message_count
            ).limit(1)
            result = await session.execute(query)
            sender = result.scalars().first()

            if sender:
                return sender
            else:
                query = select(Sender).where(
                    Sender.is_blocked == False
                ).order_by(Sender.last_message_datetime)
                result = await session.execute(query)
                sender = result.scalars().first()

                if sender and sender.last_message_datetime:
                    wait_time = (sender.last_message_datetime + timedelta(minutes=3) - datetime.now()).total_seconds()
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)
                    return await cls.get_available_sender()
                else:
                    return None
