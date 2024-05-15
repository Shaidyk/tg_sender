from datetime import datetime
from typing import List

from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, BigInteger
from sqlalchemy.orm import relationship, Mapped

from .session import BaseModel


class Client(BaseModel):
    __tablename__ = 'client'

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    username: Mapped[str] = Column(String, index=True, nullable=True)
    phone: Mapped[str] = Column(String, index=True, nullable=True)
    telegram_id: Mapped[int] = Column(BigInteger, nullable=True)

    order_statuses: Mapped[List["OrderStatus"]] = relationship("OrderStatus", back_populates="client",
                                                               cascade="all, delete-orphan",
                                                               lazy='joined')


class Sender(BaseModel):
    __tablename__ = 'sender'

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    phone: Mapped[str] = Column(String, index=True)
    password: Mapped[str] = Column(String, index=True)
    session: Mapped[str] = Column(String, index=True)
    last_message_datetime: Mapped[datetime] = Column(DateTime, nullable=True)
    is_blocked: Mapped[bool] = Column(Boolean, nullable=True, default=False)
    message_count: Mapped[int] = Column(Integer, nullable=True, default=0)


class Template(BaseModel):
    __tablename__ = 'template'

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    title: Mapped[str] = Column(String, index=True)
    text: Mapped[str] = Column(String, index=True)
    is_active: Mapped[bool] = Column(Boolean, nullable=True, default=False)
    is_archived: Mapped[bool] = Column(Boolean, nullable=True, default=False)
    files: Mapped[List["File"]] = relationship("File", back_populates="template", cascade="all, delete-orphan",
                                               lazy='joined')

    order_statuses: Mapped[List["OrderStatus"]] = relationship("OrderStatus", back_populates="template",
                                                               cascade="all, delete-orphan",
                                                               lazy='joined')


class File(BaseModel):
    __tablename__ = 'file'
    id: Mapped[int] = Column(Integer, primary_key=True)
    file_name: Mapped[str] = Column(String(255), nullable=False)
    media_type: Mapped[str] = Column(String(255), nullable=False)
    template_id: Mapped[int] = Column(Integer, ForeignKey('template.id', ondelete="CASCADE"))
    template: Mapped["Template"] = relationship("Template", back_populates="files")


class Order(BaseModel):
    __tablename__ = 'order'
    id: Mapped[int] = Column(Integer, primary_key=True)
    initiator_telegram_id: Mapped[int] = Column(BigInteger, nullable=False)
    username: Mapped[str] = Column(String(255), nullable=True)

    order_statuses: Mapped[List["OrderStatus"]] = relationship("OrderStatus", back_populates="order",
                                                               cascade="all, delete-orphan",
                                                               lazy='joined')


class OrderStatus(BaseModel):
    __tablename__ = 'order_status'
    id: Mapped[int] = Column(Integer, primary_key=True)
    message_datetime: Mapped[datetime] = Column(DateTime, nullable=False, default=datetime.now())
    is_successful: Mapped[bool] = Column(Boolean, nullable=False)
    unsuccessful_reason: Mapped[str] = Column(String, nullable=True)

    order_id: Mapped[int] = Column(Integer, ForeignKey('order.id', ondelete="CASCADE"))
    order: Mapped["Order"] = relationship("Order", back_populates="order_statuses")

    client_id: Mapped[int] = Column(Integer, ForeignKey('client.id', ondelete="CASCADE"))
    client: Mapped["Client"] = relationship("Client", back_populates="order_statuses")

    template_id: Mapped[int] = Column(Integer, ForeignKey('template.id', ondelete="CASCADE"))
    template: Mapped["Template"] = relationship("Template", back_populates="order_statuses")


class TgAdmin(BaseModel):
    __tablename__ = "tg_admin"

    id: Mapped[int] = Column(Integer, primary_key=True)
    telegram_id: Mapped[int] = Column(BigInteger, nullable=False, unique=True)
    username: Mapped[str] = Column(String, nullable=True)
    bot_chat_id: Mapped[int] = Column(BigInteger, nullable=True)
