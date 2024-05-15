# app/bot/handlers.py
import asyncio
import datetime
import json
import os
import random
import re
import uuid
from collections import defaultdict

from aiogram import Dispatcher, types, Bot, BaseMiddleware, Router, F
from aiogram.dispatcher.event.bases import CancelHandler
from aiogram.enums import ContentType, ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, FSInputFile, InputMediaPhoto, \
    InputMedia, InputMediaVideo, InputMediaDocument, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.repository.client import ClientRepository
from app.repository.order import OrderRepository
from app.repository.order_status import OrderStatusRepository
from app.repository.template import TemplateRepository
from app.repository.tg_admin import TgAdminRepository
from app.tg_bot.utils import get_cancel_kb, inline_paginator, get_template_action_keyboard
from app.repository.sender import SenderRepository
from app.tg_sender.sender import TgAccountRegistrationManager, TgSenderManager
from app.db import models

from aiogram import BaseMiddleware
from aiogram.types import Message
from typing import Callable, Dict, Any, Awaitable, List


class AdminCheckMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()

    async def __call__(self, handler, event, data):
        if isinstance(event, types.Message):
            user_id = event.from_user.id
            admin = await TgAdminRepository.get(user_id)
            if not admin:
                await event.answer("У вас нет прав администратора для использования этого бота.")
                raise CancelHandler()
        return await handler(event, data)


class AlbumMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()
        self.album_data = defaultdict(list)

    async def __call__(self, handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]], event: Message,
                       data: Dict[str, Any]):
        media_group_id = event.media_group_id
        if media_group_id:
            self.album_data[media_group_id].append(event)
            await asyncio.sleep(2)  # Для группировки сообщений в медиа-группу

            if event == self.album_data[media_group_id][-1]:
                try:
                    # Сохраняем альбом в data для последующего использования в обработчике
                    data['album'] = self.album_data.pop(media_group_id)
                    return await handler(event, data)
                except IndexError:
                    pass
        else:
            return await handler(event, data)


class SendMessageStates(StatesGroup):
    waiting_for_message_text = State()


class RegistrationStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_password = State()
    waiting_for_code = State()
    create_account = State()
    waiting_for_json = State()


class TemplateStates(StatesGroup):
    waiting_for_template_title = State()
    waiting_for_template_message = State()


class BotHandlers:
    def __init__(self, router: Router, dp: Dispatcher, bot: Bot):
        self.router = router
        self.dp = dp
        self.bot = bot
        self.dp.include_router(self.router)
        self.media_folder = 'tg_bot_media'
        if not os.path.exists(self.media_folder):
            os.makedirs(self.media_folder)
        self.register_middlewares()
        self.register_handlers()

    def register_middlewares(self):
        self.dp.message.middleware(AlbumMiddleware())
        self.dp.message.middleware(AdminCheckMiddleware())

    def register_handlers(self):
        self.setup_command_handlers()
        self.setup_callback_query_handlers()
        self.setup_inline_query_handlers()
        self.setup_message_handlers()

    # region Setup Handlers
    def setup_command_handlers(self):
        self.router.message(Command("start"))(self.handle_start_command)
        self.router.message(Command("register"))(self.handle_register_command)
        self.router.message(Command("send"))(self.handle_send_command)
        self.router.message(Command("templates"))(self.handle_templates_command)

    def setup_callback_query_handlers(self):
        self.router.callback_query(lambda c: c.data == "start")(self.handle_start_command)
        self.router.callback_query(lambda c: c.data == "register")(self.handle_register_command)
        self.router.callback_query(lambda c: c.data == "send")(self.handle_send_command)
        self.router.callback_query(lambda c: c.data == "templates")(self.handle_templates_command)

        self.router.callback_query(lambda c: c.data == "register_json")(self.register_session_json)
        self.router.callback_query(lambda c: c.data == "register_phone")(self.register_phone)
        self.router.callback_query(lambda c: c.data == "send_message")(self.callback_send_message)
        self.router.callback_query(lambda c: c.data == "process_create_template")(self.process_create_template)
        self.router.callback_query(lambda c: c.data == "create_template_title")(self.create_template_title)
        self.router.callback_query(lambda c: c.data.startswith("use_template_"))(self.use_template)
        self.router.callback_query(lambda c: c.data.startswith("show_template_"))(self.show_template_preview)
        self.router.callback_query(lambda c: c.data.startswith("delete_template_"))(self.delete_template)

    def setup_inline_query_handlers(self):
        self.router.inline_query()(self.inline_query_handler)

    def setup_message_handlers(self):
        self.router.message(StateFilter(RegistrationStates.waiting_for_phone))(self.phone_input_handler)
        self.router.message(StateFilter(RegistrationStates.waiting_for_password))(self.password_input_handler)
        self.router.message(StateFilter(RegistrationStates.waiting_for_code))(self.code_input_handler)
        self.router.message(StateFilter(RegistrationStates.waiting_for_json))(self.session_json_input_handler)
        self.router.message(StateFilter(TemplateStates.waiting_for_template_title))(
            self.create_template_title_input_handler)
        self.router.message(TemplateStates.waiting_for_template_message)(self.handle_photos)

    async def handle_incoming_message_data(self, message_data):
        try:
            admins = await TgAdminRepository.list()
            chat_ids = [admin.bot_chat_id for admin in admins]
            if ("status" in message_data) and (message_data.get("status") != 200):
                print(message_data)
            else:
                from_user = message_data.get("from_user")
                user_id = from_user.get('id')
                username = from_user.get('username')
                if username:
                    username = self.escape_markdown(username)
                client = await ClientRepository.get_client_by_tg_id(telegram_id=user_id)
                user_link = f"New message from: t.me/{client.phone} ⬆"

                # Формируем текст сообщения
                message_text = (
                    f"{message_data['text']}"
                )

                for chat_id in chat_ids:
                    # Если есть фото или видео, отправляем их с текстом
                    media = []

                    if 'photo' in message_data and message_data['photo']:
                        for index, photo in enumerate(message_data['photo']):
                            print(f"Sending photo with file_path: {photo['file_path']}")
                            media_file = FSInputFile(photo['file_path'])
                            if index == 0:
                                media.append(InputMediaPhoto(media=media_file, caption=message_text))
                            else:
                                media.append(InputMediaPhoto(media=media_file))

                    if 'video' in message_data and message_data['video']:
                        for index, video in enumerate(message_data['video']):
                            print(f"Sending video with file_path: {video['file_path']}")
                            media_file = FSInputFile(video['file_path'])
                            if index == 0 and not media:
                                media.append(InputMediaVideo(media=media_file, caption=message_text))
                            else:
                                media.append(InputMediaVideo(media=media_file))

                    if media:
                        try:
                            print("---------------------", media)
                            await self.bot.send_media_group(chat_id=chat_id, media=media)
                        except Exception as e:
                            print(f"Failed to send media group: {e}")

                        for media_item in media:
                            os.remove(media_item.media.path)  # Удаляем файл после отправки

                    # Если есть документы, отправляем их отдельно
                    if 'document' in message_data and message_data['document']:
                        for document in message_data['document']:
                            print(f"Sending document with file_path: {document['file_path']}")
                            media_file = FSInputFile(document['file_path'])
                            try:
                                await self.bot.send_document(chat_id=chat_id, document=media_file, caption=message_text)
                            except Exception as e:
                                print(f"Failed to send document: {e}")
                            os.remove(document['file_path'])

                    if not media:
                        await self.bot.send_message(chat_id=chat_id, text=message_text)
                    await self.bot.send_message(chat_id=chat_id, text=user_link)

        except Exception as e:
            print(f"Failed to send message: {e}")

    # endregion

    # region Command handlers
    async def handle_start_command(self, context: types.Union[types.Message, types.CallbackQuery]):
        await self.state_clear(context)
        user_id = context.from_user.id

        if isinstance(context, types.Message):
            chat_id = context.chat.id
        elif isinstance(context, types.CallbackQuery):
            chat_id = context.message.chat.id

        is_admin = await TgAdminRepository.get(telegram_id=user_id)
        if is_admin:
            await TgAdminRepository.update(telegram_id=user_id, bot_chat_id=chat_id)
            message_text = "Ваш bot_chat_id был успешно обновлен."
        else:
            message_text = "Вы не являетесь администратором."
        kb = [
            [InlineKeyboardButton(text="Регистрация", callback_data="register")],
            [InlineKeyboardButton(text="Рассылка сообщений", callback_data="send")],
            [InlineKeyboardButton(text="Шаблоны сообщений", callback_data="templates")]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb, resize_keyboard=True)
        message_text = "Телеграм спамер"

        if isinstance(context, types.Message):
            await context.answer(message_text, reply_markup=keyboard)
        elif isinstance(context, types.CallbackQuery):
            await context.bot.send_message(chat_id=context.from_user.id, text=message_text, reply_markup=keyboard)
            await context.answer()

    async def handle_register_command(self, context: types.Union[types.Message, types.CallbackQuery]):
        await self.state_clear(context)
        kb = [
            [InlineKeyboardButton(text="TData", callback_data="register_phone")],
            [InlineKeyboardButton(text="Session+JSON", callback_data="register_json")],
            [InlineKeyboardButton(text="Отмена ❌", callback_data="start")]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb, resize_keyboard=True)
        message_text = "Выберити тип аккаунта для регистрации"

        if isinstance(context, types.Message):
            await context.answer(message_text, reply_markup=keyboard)
        elif isinstance(context, types.CallbackQuery):
            await context.bot.send_message(chat_id=context.from_user.id, text=message_text, reply_markup=keyboard)
            await context.answer()

    async def handle_send_command(self, context: types.Union[types.Message, types.CallbackQuery]):
        await self.state_clear(context)
        kb = [
            [InlineKeyboardButton(text="Да 👌", callback_data="send_message")],
            [InlineKeyboardButton(text="Отмена ❌", callback_data="start")],
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb, resize_keyboard=True)
        templates = await TemplateRepository.list(is_active=True)
        clients = await ClientRepository.list()
        message_text = f"Вы точно хотите запустить рассылку на {len(clients)} лидов, с такими шаблонами"
        for template in templates:
            message_text += f"\n - {template.title}"
        if isinstance(context, types.Message):
            await context.answer(message_text, reply_markup=keyboard)
        elif isinstance(context, types.CallbackQuery):
            await context.bot.send_message(chat_id=context.from_user.id, text=message_text, reply_markup=keyboard)
            await context.answer()

    async def handle_templates_command(self, context: types.Union[types.Message, types.CallbackQuery]):
        await self.state_clear(context)
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="Список шаблонов", switch_inline_query_current_chat="templates"),
            InlineKeyboardButton(text="Создать", callback_data="process_create_template"),
            get_cancel_kb()[0],
            width=1
        )
        keyboard = builder.as_markup()

        message_text = f"""Для того что бы просмотреть или удалить доступные шаблоны нажмите на кнопку ниже.\n 
При нажатии на определеный шаблон вы получите его превью, а так же возможнрость удалить шаблон. Редактирование шаблонов доступно в pgAdmin """
        if isinstance(context, types.Message):
            await context.answer(message_text, reply_markup=keyboard)
        elif isinstance(context, types.CallbackQuery):
            await context.bot.send_message(chat_id=context.from_user.id, text=message_text, reply_markup=keyboard)
            await context.answer()

    # endregion

    # region Account input handlers
    async def session_json_input_handler(self, message: types.Message, state: FSMContext):
        if message.document:
            file_info = await message.bot.get_file(message.document.file_id)
            file_name = f"{uuid.uuid4()}.json"
            local_file_path = os.path.join(self.media_folder, file_name)
            await message.bot.download_file(file_info.file_path, destination=local_file_path)
            with open(local_file_path, "r") as file:
                json_data = file.read()
                data = json.loads(json_data)
                update_data = []
                for item in data:
                    if item.get("country_code"):
                        country_code = item.get("country_code")
                        phone = item.get("phone")
                        item["phone"] = country_code + phone
                        del item["country_code"]
                    update_data.append(item)
                await SenderRepository.create_bulk(update_data)
            os.remove(local_file_path)
            kb = [
                [InlineKeyboardButton(text="Назад ⬅", callback_data="register")]
            ]
            keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
            await message.answer("Аккаунты добавлены.", reply_markup=keyboard)

    async def phone_input_handler(self, message: types.Message, state: FSMContext):
        phone_number = message.text.strip().replace("+", "").replace(" ", "")
        kb = [
            [InlineKeyboardButton(text="Назад ⬅", callback_data="register")]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
        if re.match(r"^\d{10,15}$", phone_number):
            tg_account = TgAccountRegistrationManager()
            tg_account.phone = phone_number
            await state.update_data(tg_account=tg_account)
            status_message = await tg_account.connect()
            if status_message.get("status") == 200:
                await self.register_code(message, state)
            else:
                await state.clear()
                await message.reply(status_message.get("message"), reply_markup=keyboard)
        else:
            await state.clear()
            await message.reply(
                "Пожалуйста, введите номер телефона в международном формате, начиная с кода страны.",
                reply_markup=keyboard)

    async def password_input_handler(self, message: types.Message, state: FSMContext):
        password = message.text.strip()
        data = await state.get_data()
        tg_account = data.get('tg_account')
        tg_account.password = password
        await state.update_data(tg_account=tg_account)
        status_message = await tg_account.start()
        if status_message.get('status') != 200:
            await state.clear()
            message_text = status_message.get('message')
            kb = [[InlineKeyboardButton(text="Назад ⬅", callback_data="register")]]
            keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
            await message.answer(message_text, reply_markup=keyboard)
        else:
            await self.create_account(message, state)

    async def code_input_handler(self, message: types.Message, state: FSMContext):
        code = message.text.strip()
        data = await state.get_data()
        tg_account: TgAccountRegistrationManager = data.get('tg_account')
        tg_account.code = code
        status_message = await tg_account.start()
        print(f"----------------------------{status_message.get('status')}: {status_message.get('message')}")
        if status_message.get('status') == 200:
            await self.create_account(message, state)
        elif status_message.get('status') == 401:
            await self.register_password(message, state)
        elif status_message.get('status') == 406:
            await self.code_input_handler(message, state)
        else:
            pass  # TODO

    # endregion

    # region Account methods
    async def register_session_json(self, context: types.Union[types.Message, types.CallbackQuery],
                                    state: FSMContext):  # noqa
        await state.set_state(RegistrationStates.waiting_for_json)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[get_cancel_kb()])
        message_text = "Загрузите JSON файл:"

        if isinstance(context, types.Message):
            await context.answer(message_text, reply_markup=keyboard)
        elif isinstance(context, types.CallbackQuery):
            await context.bot.send_message(chat_id=context.from_user.id, text=message_text, reply_markup=keyboard)
            await context.answer()

    async def register_phone(self, context: types.Union[types.Message, types.CallbackQuery], state: FSMContext):  # noqa
        await state.set_state(RegistrationStates.waiting_for_phone)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[get_cancel_kb()])
        message_text = "Введите номер телефона:"

        if isinstance(context, types.Message):
            await context.answer(message_text, reply_markup=keyboard)
        elif isinstance(context, types.CallbackQuery):
            await context.bot.send_message(chat_id=context.from_user.id, text=message_text, reply_markup=keyboard)
            await context.answer()

    async def register_password(self, context: types.Union[types.Message, types.CallbackQuery],
                                state: FSMContext):  # noqa
        await state.set_state(RegistrationStates.waiting_for_password)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[get_cancel_kb()])
        message_text = "Введите пароль.:"

        if isinstance(context, types.Message):
            await context.answer(message_text, reply_markup=keyboard)
        elif isinstance(context, types.CallbackQuery):
            await context.bot.send_message(chat_id=context.from_user.id, text=message_text, reply_markup=keyboard)
            await context.answer()

    async def register_code(self, context: types.Union[types.Message, types.CallbackQuery], state: FSMContext):  # noqa
        await state.set_state(RegistrationStates.waiting_for_code)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[get_cancel_kb()])
        message_text = "Введите код:"

        if isinstance(context, types.Message):
            await context.answer(message_text, reply_markup=keyboard)
        elif isinstance(context, types.CallbackQuery):
            await context.bot.send_message(chat_id=context.from_user.id, text=message_text, reply_markup=keyboard)
            await context.answer()

    async def create_account(self, context: types.Union[types.Message, types.CallbackQuery], state: FSMContext):  # noqa
        data = await state.get_data()  # Retrieve stored data from the state
        await state.clear()
        tg_account: TgAccountRegistrationManager = data.get('tg_account')
        status_message = await tg_account.start()

        if status_message.get('status') == 200:
            update_data = {
                "phone": tg_account.phone,
                "password": tg_account.password,
                "session": tg_account.get_session()
            }
            await tg_account.disconnect()
            sender = await SenderRepository.create(update_data)
            await TgSenderManager().add_active_client(sender)

        kb = [[InlineKeyboardButton(text="Назад ⬅", callback_data="register")]]
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
        await state.clear()
        message_text = status_message.get('message')
        await context.bot.send_message(chat_id=context.from_user.id, text=message_text, reply_markup=keyboard)
        await context.answer(text=message_text)

    # endregion

    # region Send message methods
    async def callback_send_message(self, context: types.CallbackQuery):
        clients = await ClientRepository.list()
        templates = await TemplateRepository.get_available_templates()
        if not templates:
            kb = [
                [InlineKeyboardButton(text="Создать шаблон", callback_data="templates")],
                [InlineKeyboardButton(text="Отмена ❌", callback_data="start")]
            ]
            keyboard = InlineKeyboardMarkup(inline_keyboard=kb, resize_keyboard=True)
            await context.bot.send_message(chat_id=context.from_user.id,
                                           text=f"Нет шаблонов для рассылки.", reply_markup=keyboard)
            await context.answer()

        else:
            user_id = context.from_user.id
            username = context.from_user.username if context.from_user.username else None
            order = await OrderRepository.create(initiator_telegram_id=user_id, username=username)
            await context.bot.send_message(chat_id=context.from_user.id,
                                           text=f"Началась рассылка сообщений для ордера {order.id}")
            asyncio.create_task(self.send_messages_to_all_clients(clients, templates, user_id, order))  # noqa
            await context.answer()

    async def send_messages_to_all_clients(self, clients: List[models.Client], templates: List[models.Template],
                                           user_id, order: models.Order):
        sender = TgSenderManager()
        while clients:
            client = clients.pop(0)
            template = random.choice(templates)
            status_message = await sender.send_message_to_member(template, client)
            if status_message.get("status") == 403 or status_message.get("status") == 401:
                clients.append(client)
            elif status_message.get("status") == 200:
                await OrderStatusRepository.create(
                    is_successful=True,
                    order_id=order.id,
                    client_id=client.id,
                    template_id=template.id
                )
            else:
                await OrderStatusRepository.create(
                    is_successful=False,
                    unsuccessful_reason=status_message.get("message"),
                    order_id=order.id,
                    client_id=client.id,
                    template_id=template.id
                )

        await self.bot.send_message(chat_id=user_id, text="Рассылка сообщений завершена")

    # endregion

    # region Template input handlers
    async def create_template_title_input_handler(self, message: types.Message, state: FSMContext):
        title = message.text.strip()
        await state.update_data(title=title)
        await self.create_template_message(message, state)

    async def handle_photos(self, message: types.Message, **data):
        state = self.dp.fsm.get_context(bot=self.bot, chat_id=message.chat.id, user_id=message.from_user.id)

        if 'album' in data:
            await self.create_album_template(message, state, data)
        elif message.photo or message.video or message.document:
            await self.create_media_template(message, state)
        else:
            await self.create_text_template(message, state)

    # endregion

    # region Template methods
    async def inline_query_handler(self, inline_query: InlineQuery):
        query = inline_query.query
        offset = int(inline_query.offset) if inline_query.offset else 0
        if query == "templates":
            templates = await TemplateRepository.list()
            results = []
            for template in inline_paginator(templates, offset):
                keyboard = get_template_action_keyboard(template=template)
                title = f"{template.title} 🙂" if template.is_active else template.title
                item = InlineQueryResultArticle(
                    id=str(template.id),
                    title=title,
                    description=f'{template.text[:16]}',
                    input_message_content=InputTextMessageContent(message_text=template.text),
                    reply_markup=keyboard
                )

                results.append(item)
            if len(results) < 50:
                await inline_query.answer(results, is_personal=True, cache_time=0)
            else:
                await inline_query.answer(
                    results,
                    is_personal=True,
                    next_offset=str(offset + 50),
                    cache_time=0)

    async def process_create_template(self, context: types.Union[types.Message, types.CallbackQuery],
                                      state: FSMContext):
        kb = [[InlineKeyboardButton(text="Введите название шаблона", callback_data="create_template_title")]]
        kb.append(get_cancel_kb())
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb, resize_keyboard=True)
        await context.message.edit_text("Создание шаблона", reply_markup=keyboard)
        await context.answer()

    async def create_template_title(self, context: types.Union[types.Message, types.CallbackQuery],
                                    state: FSMContext):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[get_cancel_kb()])
        await state.set_state(TemplateStates.waiting_for_template_title)

        await context.message.edit_text("Введите название шаблона", reply_markup=keyboard)
        await context.answer()

    async def create_template_message(self, context: types.Union[types.Message, types.CallbackQuery],
                                      state: FSMContext):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[get_cancel_kb()])
        await state.set_state(TemplateStates.waiting_for_template_message)
        await context.answer("Введите текст шаблона", reply_markup=keyboard)

    async def create_album_template(self, context: types.Union[types.Message, types.CallbackQuery], state: FSMContext,
                                    data: dict) -> None:
        state_data = await state.get_data()
        title = state_data.get('title')

        files_data = []
        text = None
        for msg in data.get('album'):
            media_file = None
            ext = None
            media_type = None
            if msg.photo:
                media_file = msg.photo[-1]
                ext = "png"
                media_type = "photo"
            if msg.video:
                media_file = msg.video
                ext = media_file.mime_type.split('/')[-1]
                media_type = media_file.mime_type.split('/')[0]
            if msg.document:
                media_file = msg.document
                ext = media_file.mime_type.split('/')[-1]
                media_type = "document"

            file_info = await context.bot.get_file(media_file.file_id)
            file_name = f"{uuid.uuid4()}.{ext}"
            local_file_path = os.path.join(self.media_folder, file_name)

            await context.bot.download_file(file_info.file_path, destination=local_file_path)
            files_data.append({'file_name': file_name, "media_type": media_type})
            if not text and msg.caption:
                text = msg.caption

        template = await TemplateRepository.create(title=title, text=text, files_data=files_data)
        await state.clear()

        if template.files:
            media = []
            for index, file in enumerate(template.files):
                media_path = os.path.join(self.media_folder, file.file_name)
                media_file = FSInputFile(media_path)

                if file.media_type == "video":
                    if index == 0:
                        media.append(InputMediaVideo(media=media_file, caption=text))
                    else:
                        media.append(InputMediaVideo(media=media_file))
                if file.media_type == "photo":
                    if index == 0:
                        media.append(InputMediaPhoto(media=media_file, caption=text))
                    else:
                        media.append(InputMediaPhoto(media=media_file))
                if file.media_type == "document":
                    if index == 0:
                        media.append(InputMediaDocument(media=media_file, caption=text))
                    else:
                        media.append(InputMediaDocument(media=media_file))
            if media:
                await context.bot.send_media_group(chat_id=context.from_user.id, media=media)
        kb = [
            [InlineKeyboardButton(text="Назад ⬅", callback_data="templates")]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
        await context.answer(title, reply_markup=keyboard)

    async def create_media_template(self, context: types.Union[types.Message, types.CallbackQuery],
                                    state: FSMContext) -> None:
        state_data = await state.get_data()
        title = state_data.get('title')
        media_file = None
        ext = None
        media_type = None
        if context.photo:
            media_file = context.photo[-1]
            ext = "png"
            media_type = "photo"
        if context.video:
            media_file = context.video
            ext = media_file.mime_type.split('/')[-1]
            media_type = media_file.mime_type.split('/')[0]
        if context.document:
            media_file = context.document
            ext = media_file.mime_type.split('/')[-1]
            media_type = "document"

        file_info = await context.bot.get_file(media_file.file_id)
        file_name = f"{uuid.uuid4()}.{ext}"
        local_file_path = os.path.join(self.media_folder, file_name)
        await context.bot.download_file(file_info.file_path, destination=local_file_path)
        files_data = [{'file_name': file_name, "media_type": media_type}]
        text = context.caption if context.caption else state_data.get('text', None)
        template = await TemplateRepository.create(title=title, text=text, files_data=files_data)
        await state.clear()

        if template.files:
            media = []
            for index, file in enumerate(template.files):
                media_path = os.path.join(self.media_folder, file.file_name)
                media_file = FSInputFile(media_path)
                if media_type == "video":
                    media.append(InputMediaVideo(media=media_file, caption=text))
                if media_type == "photo":
                    media.append(InputMediaPhoto(media=media_file, caption=text))
                if media_type == "document":
                    media.append(InputMediaDocument(media=media_file, caption=text))
            if media:
                await context.bot.send_media_group(chat_id=context.from_user.id, media=media)

        kb = [
            [InlineKeyboardButton(text="Назад ⬅", callback_data="templates")]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
        await context.answer(title, reply_markup=keyboard)

    async def create_text_template(self, context: types.Union[types.Message, types.CallbackQuery],
                                   state: FSMContext) -> None:
        state_data = await state.get_data()
        title = state_data.get('title')

        text = context.caption if context.caption else state_data.get('text', None)
        text = context.text if context.text else text
        await TemplateRepository.create(title=title, text=text)
        await state.clear()

        await context.answer(text)
        kb = [
            [InlineKeyboardButton(text="Назад ⬅", callback_data="templates")]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
        await context.answer(title, reply_markup=keyboard)

    async def use_template(self, context: types.CallbackQuery):
        template_id = context.data.split("_")[-1]
        template: models.Template = await TemplateRepository.get(int(template_id))
        if not template.is_active:
            message_text = f"Шаблон \"{template.title}\" активирован."
        else:
            message_text = f"Шаблон \"{template.title}\" отключен."

        await TemplateRepository.update(template_id=template.id, is_active=not template.is_active)

        await context.bot.send_message(chat_id=context.from_user.id, text=message_text)
        await context.answer()

    async def show_template_preview(self, context: types.CallbackQuery):
        template_id = int(context.data.split('_')[-1])
        template = await TemplateRepository.get(template_id)

        title = template.title
        text = template.text
        kb = [
            [InlineKeyboardButton(text="Назад ⬅", callback_data="templates")]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
        if template.files:
            media = []
            for index, file in enumerate(template.files):
                media_path = os.path.join(self.media_folder, file.file_name)
                media_file = FSInputFile(media_path)

                if file.media_type == "video":
                    if index == 0:
                        media.append(InputMediaVideo(media=media_file, caption=text))
                    else:
                        media.append(InputMediaVideo(media=media_file))
                if file.media_type == "photo":
                    if index == 0:
                        media.append(InputMediaPhoto(media=media_file, caption=text))
                    else:
                        media.append(InputMediaPhoto(media=media_file))
                if file.media_type == "document":
                    if index == 0:
                        media.append(InputMediaDocument(media=media_file, caption=text))
                    else:
                        media.append(InputMediaDocument(media=media_file))
            if media:
                await context.bot.send_media_group(chat_id=context.from_user.id, media=media)
                await context.bot.send_message(chat_id=context.from_user.id, text=title, reply_markup=keyboard)
            else:
                await context.bot.send_message(chat_id=context.from_user.id, text=text, reply_markup=keyboard)
        else:
            await context.bot.send_message(chat_id=context.from_user.id, text=text, reply_markup=keyboard)
        await context.answer()

    async def delete_template(self, context: types.CallbackQuery):
        template_id = context.data.split("_")[-1]
        template: models.Template = await TemplateRepository.get(int(template_id))
        await TemplateRepository.delete(template_id=template.id)
        message_text = f"Шаблон \"{template.title}\" удалён."
        await context.bot.send_message(chat_id=context.from_user.id, text=message_text)
        await context.answer()

    # endregion

    # region Utils
    async def state_clear(self, context: types.Union[types.Message, types.CallbackQuery]):
        state = None
        if isinstance(context, types.CallbackQuery):
            state = self.dp.fsm.get_context(bot=self.bot, chat_id=context.from_user.id, user_id=context.from_user.id)
        elif isinstance(context, types.Message):
            state = self.dp.fsm.get_context(bot=self.bot, chat_id=context.chat.id, user_id=context.from_user.id)
        if state:
            await state.clear()

    def escape_markdown(self, text):
        # Экранирование символов для Markdown
        escape_chars = r'\_*`['
        return re.sub(f'([{escape_chars}])', r'\\\1', text)
    # endregion
