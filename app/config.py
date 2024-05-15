# config.py
import os
from os import environ
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv


class Settings(BaseSettings):
    class Config:
        env_file = Path(__file__).parent.joinpath("../.env").resolve(True)

    # Telegram
    TG_BOT_TOKEN: str

    # Telegram API
    API_ID: int
    API_HASH: str

    # Database
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    PGDATA: str

    @property
    def DATABASE_URL(self):
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


settings = Settings()
