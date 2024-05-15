from datetime import datetime
from typing import List

from pydantic import BaseModel


class ClientBase(BaseModel):
    username: str
    phone: str
    offer_statuses: List['OfferStatus']


class ClientCreate(ClientBase):
    pass


class Client(ClientBase):
    id: int
    username: str
    phone: str
    offer_statuses: List['OfferStatus']

    class Config:
        orm_mode = True


class SenderBase(BaseModel):
    phone: str
    password: str
    session: str


class SenderCreate(SenderBase):
    pass


class Sender(SenderBase):
    id: int
    phone: str
    password: str
    session: str
    last_message_datetime: datetime = None
    is_blocked: bool = False
    message_count: int = 0

    class Config:
        orm_mode = True


class TemplateBase(BaseModel):
    title: str
    text: str
    is_active: bool = False
    is_archived: bool = False
    file_name: str
    files: List['File']
    offer_statuses: List['OfferStatus']


class TemplateCreate(TemplateBase):
    pass


class Template(TemplateBase):
    id: int
    title: str
    text: str
    is_active: bool = False
    is_archived: bool = False
    files: List['File']
    offer_statuses: List['OfferStatus']

    class Config:
        orm_mode = True


class FileBase(BaseModel):
    file_name: str
    media_type: str
    template_id: int
    template: 'Template'


class FileCreate(FileBase):
    pass


class File(FileBase):
    id: int
    file_name: str
    media_type: str
    template_id: int
    template: 'Template'

    class Config:
        orm_mode = True


class OfferBase(BaseModel):
    initiator_telegram_id: int
    username: str
    offer_statuses: List['OfferStatus']


class OfferCreate(OfferBase):
    pass


class Offer(OfferBase):
    id: int
    initiator_telegram_id: int
    username: str
    offer_statuses: List['OfferStatus']

    class Config:
        orm_mode = True


class OfferStatusBase(BaseModel):
    message_datetime: str
    is_successful: bool
    unsuccessful_reason: str

    offer_id: int
    offer: 'Offer'

    client_id: int
    client: 'Client'

    template_id: int
    template: 'Template'


class OfferStatusCreate(OfferStatusBase):
    pass


class OfferStatus(OfferStatusBase):
    id: int
    message_datetime: str
    is_successful: bool
    unsuccessful_reason: str

    offer_id: int
    offer: 'Offer'

    client_id: int
    client: 'Client'

    template_id: int
    template: 'Template'

    class Config:
        orm_mode = True


class TgAdminBase(BaseModel):
    telegram_id: int
    username: str
    bot_chat_id: int


class TgAdminCreate(OfferStatusBase):
    pass


class TgAdminStatus(OfferStatusBase):
    id: int
    telegram_id: int
    username: str
    bot_chat_id: int

    class Config:
        orm_mode = True
