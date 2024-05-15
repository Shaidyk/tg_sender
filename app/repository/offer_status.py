from sqlalchemy import select, delete
from sqlalchemy.orm import joinedload

from app.db.models import OfferStatus
from app.db.session import db_session


class OfferStatusRepository:
    @classmethod
    async def list(cls, **kwargs):
        async with db_session() as session:
            query = select(OfferStatus).options(joinedload(OfferStatus.offer), joinedload(OfferStatus.client),
                                                joinedload(OfferStatus.template))

            for key, value in kwargs.items():
                if hasattr(OfferStatus, key):
                    query = query.filter(getattr(OfferStatus, key) == value)

            result = await session.execute(query)
            return result.scalars().all()

    @classmethod
    async def get(cls, status_id: int):
        async with db_session() as session:
            result = await session.execute(select(OfferStatus).where(OfferStatus.id == status_id))
            return result.scalars().first()

    @classmethod
    async def update(cls, status_id: int, **kwargs):
        async with db_session() as session:
            result = await session.execute(select(OfferStatus).where(OfferStatus.id == status_id))
            status = result.scalar()
            if status is None:
                raise ValueError("Status not found")

            for key, value in kwargs.items():
                if hasattr(OfferStatus, key):
                    setattr(status, key, value)

            await session.commit()
            return status

    @classmethod
    async def create(cls, **kwargs):
        async with db_session() as session:
            new_status = OfferStatus(**kwargs)
            session.add(new_status)
            await session.commit()
            await session.refresh(new_status)
            return new_status

    @classmethod
    async def delete(cls, status_id: int):
        async with db_session() as session:
            result = await session.execute(delete(OfferStatus).where(OfferStatus.id == status_id))
            await session.commit()
            return result.rowcount
