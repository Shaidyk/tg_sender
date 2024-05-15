from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_cancel_kb():
    return [InlineKeyboardButton(text="Отмена ❌", callback_data="start")]


def get_template_list_button():
    return InlineKeyboardButton(
        text="Шаблоны",
        switch_inline_query_current_chat="templates"
    )


def get_templates_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        get_template_list_button(),
        get_cancel_kb()[0],
        width=1
    )
    return builder.as_markup()


def get_template_action_keyboard(template):
    action_button_text = "Использовать ✅" if not template.is_active else "Отключить 🚫"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=action_button_text, callback_data=f"use_template_{template.id}")],
        [InlineKeyboardButton(text="Показать превтю шаблона 👀", callback_data=f"show_template_{template.id}")],
        [InlineKeyboardButton(text="Удалить 🗑", callback_data=f"delete_template_{template.id}")],
        [InlineKeyboardButton(text="Назад ⬅", callback_data="templates")]
    ])


def inline_paginator(data: list, start_num: int) -> list:
    size = 50
    overall_items = len(data)

    if overall_items <= 50:
        return data

    if start_num >= overall_items:
        return []

    elif start_num + size >= overall_items:
        return data[start_num:overall_items]
    else:
        return data[start_num: start_num + size]
