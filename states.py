from aiogram.fsm.state import State, StatesGroup

class Registration(StatesGroup):
    name = State()
    gender = State()
    age = State()
    city = State()
    bio = State()
    photo = State()

class Search(StatesGroup):
    city = State()
    age_range = State()

class TaskAnswer(StatesGroup):
    waiting_for_answer = State()

class Payment(StatesGroup):
    waiting_for_confirmation = State()
    waiting_for_coupon = State()
    waiting_for_balance_coupon = State()

class Referral(StatesGroup):
    waiting_for_code = State()

class Admin(StatesGroup):
    waiting_for_coupon_code = State()
    waiting_for_discount = State()
    waiting_for_max_uses = State()
    waiting_for_amount_coupon_code = State()
    waiting_for_amount_value = State()
    waiting_for_amount_max_uses = State()
    waiting_for_coupon_amount = State()