import asyncio
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command

from app.config import settings
from app.tg_bot.handlers import BotHandlers
from app.tg_sender.sender import TgSenderManager

app = FastAPI()

# bot = Bot(token=settings.TG_BOT_TOKEN)
# dp = Dispatcher()
# router = Router()
#
# handlers = BotHandlers(router, dp, bot)
#
# @app.on_event("startup")
# async def init_account_manager():
#     account_manager = TgSenderManager(handlers)
#     await account_manager.load_and_init_clients()
#     return account_manager
#
#
# async def start_bot():
#     await dp.start_polling(bot)
#
#
# @app.on_event("startup")
# async def startup_event():
#     asyncio.create_task(start_bot())  # noqa
