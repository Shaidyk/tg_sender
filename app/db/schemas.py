from datetime import datetime
from typing import List

from pydantic import BaseModel


class ClientBase(BaseModel):
    username: str
    phone: str
    order_statuses: List['OrderStatus']


class ClientCreate(ClientBase):
    pass


class Client(ClientBase):
    id: int
    username: str
    phone: str
    order_statuses: List['OrderStatus']

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
    order_statuses: List['OrderStatus']


class TemplateCreate(TemplateBase):
    pass


class Template(TemplateBase):
    id: int
    title: str
    text: str
    is_active: bool = False
    is_archived: bool = False
    files: List['File']
    order_statuses: List['OrderStatus']

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


class OrderBase(BaseModel):
    initiator_telegram_id: int
    username: str
    order_statuses: List['OrderStatus']


class OrderCreate(OrderBase):
    pass


class Order(OrderBase):
    id: int
    initiator_telegram_id: int
    username: str
    order_statuses: List['OrderStatus']

    class Config:
        orm_mode = True


class OrderStatusBase(BaseModel):
    message_datetime: str
    is_successful: bool
    unsuccessful_reason: str

    order_id: int
    order: 'Order'

    client_id: int
    client: 'Client'

    template_id: int
    template: 'Template'


class OrderStatusCreate(OrderStatusBase):
    pass


class OrderStatus(OrderStatusBase):
    id: int
    message_datetime: str
    is_successful: bool
    unsuccessful_reason: str

    order_id: int
    order: 'Order'

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


class TgAdminCreate(OrderStatusBase):
    pass


class TgAdminStatus(OrderStatusBase):
    id: int
    telegram_id: int
    username: str
    bot_chat_id: int

    class Config:
        orm_mode = True
