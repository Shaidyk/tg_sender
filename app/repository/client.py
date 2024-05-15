from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from app.db.models import Client, OfferStatus
from app.db.session import db_session


class ClientRepository:
    @classmethod
    async def list(cls, **kwargs):
        async with db_session() as session:
            query = select(Client).options(
                joinedload(Client.offer_statuses).joinedload(OfferStatus.offer)
            )
            for key, value in kwargs.items():
                if hasattr(Client, key):
                    query = query.filter(getattr(Client, key) == value)

            result = await session.execute(query)
            return result.scalars().unique().all()


    @classmethod
    async def get_client(cls, client_id: int):
        async with db_session() as session:
            result = await session.execute(select(Client).filter(Client.id == client_id))
            return result.scalars().first()

    @classmethod
    async def create_client(cls, client_data: dict):
        async with db_session() as session:
            client = Client(**client_data)
            session.add(client)
            await session.commit()
            await session.refresh(client)
            return client
