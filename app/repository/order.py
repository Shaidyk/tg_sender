from sqlalchemy import select, delete
from sqlalchemy.orm import joinedload

from app.db.models import Order
from app.db.session import db_session


class OrderRepository:
    @classmethod
    async def list(cls, **kwargs):
        async with db_session() as session:
            query = select(Order).options(joinedload(Order.order_statuses))

            for key, value in kwargs.items():
                if hasattr(Order, key):
                    query = query.filter(getattr(Order, key) == value)

            result = await session.execute(query)
            return result.scalars().unique().all()

    @classmethod
    async def get(cls, order_id: int):
        async with db_session() as session:
            result = await session.execute(select(Order).filter(Order.id == order_id))
            return result.scalars().first()

    @classmethod
    async def update(cls, template_id: int, **kwargs):
        async with db_session() as session:
            result = await session.execute(select(Order).filter(Order.id == template_id))
            order = result.scalar()
            if order is None:
                raise ValueError("Template not found")

            for key, value in kwargs.items():
                if hasattr(Order, key):
                    setattr(order, key, value)

            await session.commit()
            return order

    @classmethod
    async def create(cls, **kwargs):
        async with db_session() as session:
            new_order = Order(**kwargs)
            session.add(new_order)

            await session.commit()
            await session.refresh(new_order)
            return new_order

    @classmethod
    async def delete(cls, order_id: int):
        async with db_session() as session:
            result = await session.execute(delete(Order).where(Order.id == order_id))
            await session.commit()
            return result.rowcount
