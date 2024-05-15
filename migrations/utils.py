from asyncpg import connect as async_pg_connect, InvalidCatalogNameError


# Database creation.
async def create_database_if_not_exists(database_name: str):
    try:
        conn = await async_pg_connect(
            host="db",
            port=5432,
            user="admin",
            password="admin",
            database="tg_sender_db"
        )
    except InvalidCatalogNameError:
        sys_conn = await async_pg_connect(
            host="db",
            port=5432,
            user="admin",
            password="admin",
            database='postgres'
        )
        await sys_conn.execute(
            f'CREATE DATABASE "{database_name}" OWNER "{"admin"}"'
        )
        await sys_conn.close()
    else:
        await conn.close()
