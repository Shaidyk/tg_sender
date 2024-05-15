from sqlalchemy import select, delete
from sqlalchemy.orm import joinedload

from app.db.models import Offer
from app.db.session import db_session


class OfferRepository:
    @classmethod
    async def list(cls, **kwargs):
        async with db_session() as session:
            query = select(Offer).options(joinedload(Offer.offer_statuses))

            for key, value in kwargs.items():
                if hasattr(Offer, key):
                    query = query.filter(getattr(Offer, key) == value)

            result = await session.execute(query)
            return result.scalars().unique().all()

    @classmethod
    async def get(cls, offer_id: int):
        async with db_session() as session:
            result = await session.execute(select(Offer).filter(Offer.id == offer_id))
            return result.scalars().first()

    @classmethod
    async def update(cls, template_id: int, **kwargs):
        async with db_session() as session:
            result = await session.execute(select(Offer).filter(Offer.id == template_id))
            offer = result.scalar()
            if offer is None:
                raise ValueError("Template not found")

            for key, value in kwargs.items():
                if hasattr(Offer, key):
                    setattr(offer, key, value)

            await session.commit()
            return offer

    @classmethod
    async def create(cls, **kwargs):
        async with db_session() as session:
            new_offer = Offer(**kwargs)
            session.add(new_offer)

            await session.commit()
            await session.refresh(new_offer)
            return new_offer

    @classmethod
    async def delete(cls, offer_id: int):
        async with db_session() as session:
            result = await session.execute(delete(Offer).where(Offer.id == offer_id))
            await session.commit()
            return result.rowcount
