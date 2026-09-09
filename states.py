# -*- coding: utf-8 -*-
"""FSM holatlari — hammasi bitta joyda, nomlar bo'yicha guruhlangan."""
from aiogram.fsm.state import State, StatesGroup


class BronState(StatesGroup):
    search_pharmacy = State()
    waiting_quantity = State()


class DrugState(StatesGroup):
    name = State()
    unit = State()
    price = State()
    nds_rate = State()
    box_capacity = State()
    edit_value = State()


class PharmacyState(StatesGroup):
    inn = State()
    inn_confirm = State()
    name = State()
    region = State()
    manager = State()
    phone = State()

    edit_search = State()
    edit_field = State()
    edit_value = State()


class UserState(StatesGroup):
    telegram_id = State()
    full_name = State()
    role = State()


class CompanyState(StatesGroup):
    edit_value = State()


class InfoState(StatesGroup):
    search = State()
