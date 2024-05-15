from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from app.db.models import Template, File
from app.db.session import db_session


class TemplateRepository:
    @classmethod
    async def list(cls, **kwargs):
        async with db_session() as session:
            query = select(Template).options(joinedload(Template.files), joinedload(Template.offer_statuses))

            for key, value in kwargs.items():
                if hasattr(Template, key):
                    query = query.filter(getattr(Template, key) == value)

            result = await session.execute(query)
            return result.scalars().unique().all()

    @classmethod
    async def get_available_templates(cls):
        async with db_session() as session:
            query = select(Template).options(joinedload(Template.files)).\
                filter(Template.is_active == True, Template.is_archived == False)
            result = await session.execute(query)
            return result.scalars().unique().all()

    @classmethod
    async def get_by_title(cls, title: str):
        async with db_session() as session:
            result = await session.execute(select(Template).filter(Template.title == title))
            return result.scalars().first()

    @classmethod
    async def get(cls, template_id: int):
        async with db_session() as session:
            result = await session.execute(select(Template).filter(Template.id == template_id))
            return result.scalars().first()

    @classmethod
    async def update(cls, template_id: int, **kwargs):
        async with db_session() as session:
            result = await session.execute(select(Template).filter(Template.id == template_id))
            template = result.scalar()
            if template is None:
                raise ValueError("Template not found")

            for key, value in kwargs.items():
                if hasattr(Template, key):
                    setattr(template, key, value)

            await session.commit()
            return template

    @classmethod
    async def delete(cls, template_id: int):
        async with db_session() as session:
            result = await session.execute(delete(Template).where(Template.id == template_id))
            await session.commit()
            return result.rowcount

    @classmethod
    async def get_with_files(cls, template_id: int):
        async with db_session() as session:
            result = await session.execute(
                select(Template).options(joinedload(Template.files)).filter(Template.id == template_id))
            return result.scalars().first()

    @classmethod
    async def create(cls, title, text, files_data=None):
        async with db_session() as session:
            new_template = Template(title=title, text=text)
            session.add(new_template)
            await session.flush()

            if files_data:
                for file_data in files_data:
                    file = File(file_name=file_data['file_name'], media_type=file_data['media_type'],
                                template=new_template)
                    session.add(file)

            await session.commit()
            await session.refresh(new_template)
            return new_template
