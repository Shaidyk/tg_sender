import asyncio
import datetime
import os
import random

from telethon import TelegramClient, events
from telethon.errors import UserDeactivatedBanError, FloodWaitError, RPCError, SecurityError, UserDeactivatedError, \
    SessionPasswordNeededError
from telethon.sessions import StringSession
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact, PeerUser, MessageMediaPhoto, MessageMediaDocument, PhotoSize, \
    DocumentAttributeFilename

from app.db.models import Sender
from app.repository.sender import SenderRepository
from app.config import settings
from app.repository.tg_admin import TgAdminRepository


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class TgAccountRegistrationManager:
    CONNECTION_RETRIES = 1

    def __init__(self):
        self.phone = None
        self.password = None
        self.code = None
        self.session = None

        self.phone_hash_code = None
        self.client: TelegramClient | None = None
        self.status_message: dict = {}

    async def connect(self):
        if self.client:
            await self.client.disconnect()
        print("Connecting to Telegram...")

        sender = await SenderRepository.get(phone=self.phone)
        if sender and sender.session:
            self.status_message = {"status": 409, "message": f"Account with phone {sender.phone} already exists"}
            return self.status_message
        else:
            self.session = StringSession()

        self.client = TelegramClient(
            session=self.session,
            api_id=settings.API_ID,
            api_hash=settings.API_HASH,
            connection_retries=self.CONNECTION_RETRIES,
        )

        try:
            await asyncio.wait_for(self.client.connect(), timeout=10)
            result = await self.client.send_code_request(self.phone)
            self.phone_hash_code = result.phone_code_hash
            self.status_message = {"status": 200, "message": f"Connected successfully."}
        except (RPCError, SecurityError) as e:
            self.status_message = {"status": e.code, "message": f"{e}"}
        except asyncio.TimeoutError:
            self.status_message = {"status": 408, "message": "Connection timed out."}
        except Exception as e:
            self.status_message = {"status": 500, "message": f"Unexpected error: {e}"}

        return self.status_message

    async def start(self):
        if self.code:
            try:
                if not self.password:
                    await self.client.sign_in(
                        phone=self.phone,
                        code=self.code,
                        phone_code_hash=self.phone_hash_code
                    )
                else:
                    await self.client.sign_in(
                        phone=self.phone,
                        password=self.password,
                        code=self.code,
                        phone_code_hash=self.phone_hash_code
                    )
                self.status_message = {"status": 200, "message": "Successfully logged in."}
            except SessionPasswordNeededError as e:
                self.status_message = {"status": e.code, "message": f"{e}"}
            except (RPCError, SecurityError) as e:
                self.status_message = {"status": e.code, "message": f"{e}"}
            except Exception as e:
                self.status_message = {"status": 500, "message": f"Unexpected error: {e}"}
            return self.status_message
        else:
            self.status_message = {"status": 406, "message": "No code provided."}
            return self.status_message

    async def disconnect(self):
        if self.client:
            self.client.disconnect()

    def get_session(self):
        return self.client.session.save()


class TgSenderManager(metaclass=SingletonMeta):
    CONNECTION_RETRIES = 1

    def __init__(self, bot_handlers):
        self.bot_handlers = bot_handlers
        self.active_clients = {}
        self.media_folder = 'tg_bot_media'
        self.media_group_data = {}
        self.media_group_tasks = {}

    async def add_active_client(self, sender):
        sender = await SenderRepository.get_by_id(sender.id)
        await self.connect(sender)

    async def load_and_init_clients(self):
        senders: list[Sender] = await SenderRepository.list(is_blocked=False)

        for sender in senders:
            if not sender.session:
                self.status_message = {"status": 409, "message": f"No session found for {sender.phone}, skipping."}
                return self.status_message

            await self.connect(sender)

    async def connect(self, sender):
        client = TelegramClient(
            session=StringSession(sender.session),
            api_id=settings.API_ID,
            api_hash=settings.API_HASH,
            connection_retries=self.CONNECTION_RETRIES,
        )
        try:
            await asyncio.wait_for(client.connect(), timeout=10)

            if await client.is_user_authorized():
                client.add_event_handler(self.handle_new_message, events.NewMessage)
                await asyncio.wait_for(client.start(), timeout=10)
                self.active_clients[sender.id] = client
                self.status_message = {"status": 200, "message": f"Sender ID: {sender.id}. Success started."}
            else:
                self.status_message = {"status": 403, "message": f"Sender ID: {sender.id}. User not connected."}
        except UserDeactivatedBanError as e:
            self.status_message = {"status": 403, "message": f"Sender ID: {sender.id}. {e}"}
            await SenderRepository.update(sender_id=sender.id, is_blocked=True)
        except asyncio.TimeoutError:
            self.status_message = {"status": 408, "message": "Sender ID: {sender.id}. Connection timed out."}
        except (RPCError, SecurityError) as e:
            self.status_message = {"status": e.code, "message": f"Sender ID: {sender.id}. {e}"}
        except Exception as e:
            self.status_message = {"status": 500, "message": f"Sender ID: {sender.id}. Unexpected error: {e}"}

        return client

    async def send_message_to_member(self, template, username: str = None, phone: str = None):
        sender = await SenderRepository.get_available_sender()
        client = self.active_clients.get(sender.id)

        try:
            contact_data = None
            if phone and isinstance(phone, str):
                phone = phone.replace(" ", "").replace("+", "")
                if phone.isnumeric():
                    contact = InputPhoneContact(client_id=0, phone=phone, first_name="NewUser", last_name=" ")
                    result = await client(ImportContactsRequest([contact]))
                    if not result.imported:
                        self.status_message = {"status": 404, "message": f"Lead {phone} not imported."}
                        return self.status_message
                    contact_data = result.users[0]
                else:
                    self.status_message = {"status": 400, "message": f"Invalid phone format: {phone}."}
                    return self.status_message
            elif phone and isinstance(phone, int):
                contact = InputPhoneContact(client_id=0, phone=str(phone), first_name="Andrey", last_name=" ")
                result = await client(ImportContactsRequest([contact]))
                if not result.imported:
                    self.status_message = {"status": 404, "message": f"Lead {phone} not imported."}
                    return self.status_message
                contact_data = result.users[0]
            elif username:
                contact_data = username
            else:
                self.status_message = {"status": 400, "message": "Lead username and phone number is None"}
                return self.status_message

            user = await client.get_input_entity(contact_data)
            media_group = []
            if template.files:
                for file in template.files:
                    file_path = os.path.join(self.media_folder, file.file_name)
                    if os.path.exists(file_path):
                        uploaded_file = await client.upload_file(file_path)
                        media_group.append(uploaded_file)

            if media_group:
                await client.send_file(user, media_group, caption=template.text)
            else:
                await client.send_message(user, template.text)

            await SenderRepository.update(
                sender_id=sender.id,
                last_message_datetime=datetime.datetime.now(),
                message_count=sender.message_count + 1
            )

            self.status_message = {"status": 200, "message": f"Sender ID: {sender.id}. Sussessfully sent"}
        except (UserDeactivatedBanError, UserDeactivatedError) as e:
            self.status_message = {"status": e.code, "message": f"Sender ID: {sender.id}. {e}"}
            await SenderRepository.update(sender_id=sender.id, is_blocked=True)
            return self.status_message
        except FloodWaitError as e:
            wait_until = datetime.datetime.now() + datetime.timedelta(seconds=e.seconds)
            await SenderRepository.update(sender_id=sender.id, last_message_datetime=wait_until)
            self.status_message = {"status": 403, "message": f"Sender ID: {sender.id}. {e}"}
        except (RPCError, SecurityError) as e:
            self.status_message = {"status": e.code, "message": f"Sender ID: {sender.id}. {e}"}
        except Exception as e:
            self.status_message = {"status": 500, "message": f"Sender ID: {sender.id}. Unexpected error: {e}"}
        return self.status_message

    async def handle_new_message(self, event: events.NewMessage.Event):
        if event.is_private:
            client_id = None
            for id, client in self.active_clients.items():
                if client == event.client:
                    client_id = id
                    break

            if client_id is not None:
                sender = await SenderRepository.get_by_id(client_id)
                if sender:
                    try:
                        # Получаем идентификатор пользователя из peer_id
                        user_id = event.message.peer_id.user_id if isinstance(event.message.peer_id, PeerUser) else None

                        # Формируем данные сообщения
                        photo_paths = []
                        document_paths = []
                        video_paths = []

                        if isinstance(event.message.media, MessageMediaPhoto):
                            file_path = await event.message.download_media(file=self.media_folder)
                            photo_paths.append({
                                "file_path": file_path,
                                "width": event.message.media.photo.sizes[-1].w,
                                "height": event.message.media.photo.sizes[-1].h,
                                "file_size": getattr(event.message.media.photo.sizes[-1], 'size', None)
                            })

                        if isinstance(event.message.media, MessageMediaDocument):
                            file_path = await event.message.download_media(file=self.media_folder)
                            document_data = {
                                "file_path": file_path,
                                "file_name": None,
                                "mime_type": event.message.media.document.mime_type,
                                "file_size": event.message.media.document.size
                            }
                            for attribute in event.message.media.document.attributes:
                                if isinstance(attribute, DocumentAttributeFilename):
                                    document_data["file_name"] = attribute.file_name
                                    break
                            # Если документ является видео
                            if 'video' in event.message.media.document.mime_type:
                                video_paths.append(document_data)
                            else:
                                document_paths.append(document_data)

                        message_data = {
                            "message_id": event.message.id,
                            "from_user": {
                                "id": user_id,
                                "is_bot": False,
                                "first_name": event.message.sender.first_name if event.message.sender and event.message.sender.first_name else None,
                                "last_name": event.message.sender.last_name if event.message.sender and event.message.sender.last_name else None,
                                "username": event.message.sender.username if event.message.sender and event.message.sender.username else None
                            },
                            "date": event.message.date,
                            "text": event.message.message,
                            "photo": photo_paths,
                            "document": document_paths,
                            "video": video_paths,
                            "media_group_id": event.message.grouped_id  # Добавляем идентификатор медиагруппы
                        }

                        # Обработка входящего сообщения
                        await self.process_message_data(message_data)

                    except Exception as e:
                        print(f"Error handling new message: {e}")

    async def process_message_data(self, message_data):
        media_group_id = message_data.get("media_group_id")

        if media_group_id:
            if media_group_id not in self.media_group_data:
                self.media_group_data[media_group_id] = []

            self.media_group_data[media_group_id].append(message_data)

            if media_group_id in self.media_group_tasks:
                self.media_group_tasks[media_group_id].cancel()

            self.media_group_tasks[media_group_id] = asyncio.create_task(self.wait_and_send_media_group(media_group_id))
        else:
            await self.bot_handlers.handle_incoming_message_data(message_data)

    async def wait_and_send_media_group(self, media_group_id):
        await asyncio.sleep(20)

        if media_group_id in self.media_group_data:
            combined_message_data = {
                "message_id": self.media_group_data[media_group_id][0]["message_id"],
                "from_user": self.media_group_data[media_group_id][0]["from_user"],
                "date": self.media_group_data[media_group_id][0]["date"],
                "text": "\n".join([msg["text"] for msg in self.media_group_data[media_group_id]]),
                "photo": sum([msg["photo"] for msg in self.media_group_data[media_group_id]], []),
                "document": sum([msg["document"] for msg in self.media_group_data[media_group_id]], []),
                "video": sum([msg["video"] for msg in self.media_group_data[media_group_id]], []),
            }
            await self.bot_handlers.handle_incoming_message_data(combined_message_data)
            del self.media_group_data[media_group_id]
            del self.media_group_tasks[media_group_id]
