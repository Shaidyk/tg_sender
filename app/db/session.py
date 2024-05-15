from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncAttrs
from sqlalchemy.orm import sessionmaker, declarative_base, DeclarativeBase
from sqlalchemy import event, Select

from app.config import settings


class BaseModel(AsyncAttrs, DeclarativeBase):
    pass


SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True)

sync_maker = sessionmaker()
db_session = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    future=True,
    sync_session_class=sync_maker,
)


def clear_cache(conn, clauseelement, multiparams, params):
    if isinstance(clauseelement, Select):
        return


def setup_listeners():
    event.listen(engine.sync_engine, "before_execute", clear_cache)


setup_listeners()
