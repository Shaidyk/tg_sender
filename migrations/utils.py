from asyncpg import connect as async_pg_connect, InvalidCatalogNameError
from app.config import settings


# Database creation.
async def create_database_if_not_exists(database_name: str):
    try:
        conn = await async_pg_connect(
            host=settings.POSTGRES_DB,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB
        )
    except InvalidCatalogNameError:
        sys_conn = await async_pg_connect(
            host=settings.POSTGRES_DB,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB
        )
        await sys_conn.execute(
            f'CREATE DATABASE "{database_name}" OWNER "{settings.POSTGRES_USER}"'
        )
        await sys_conn.close()
    else:
        await conn.close()
