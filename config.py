# config.py
import os
import secrets

# === Токены ===
BOT_TOKEN = "7458257831:AAHtsHC9FSTi-r0VRCBJMJ504Zhlk1x5Kr4"
CRYPTO_BOT_TOKEN = "447765:AAASEFBfCAs2IZLVxfIDYoxHhGS0ZFZ1Ql3"

# === Настройки заданий ===
REGULAR_TASKS_COUNT = 5  # Количество обычных заданий перед открытием чата
ROMANTIC_TASKS_COUNT = 3  # Количество романтических заданий

# === Цены ===
ROMANTIC_TOUR_PRICE = 2.0  # Цена романтического тура
SUPER_LIKE_PRICE = 1.0  # Цена супер-лайка (показывает анкету в топе)
BOOST_PROFILE_PRICE = 3.0  # Цена буста профиля (показывает анкету чаще)
SEE_WHO_LIKED_PRICE = 2.0  # Цена просмотра кто поставил лайк

# === Реферальная система ===
REFERRAL_BONUS = 1.0  # Бонус за реферала

# === Задания ===
REGULAR_TASKS = [
    "Расскажи о своем самом ярком воспоминании из детства",
    "Какая твоя любимая книга или фильм и почему?",
    "Опиши идеальное свидание в трех словах",
    "Какая твоя самая большая мечта?",
    "Расскажи о самом смешном случае из твоей жизни"
]

ROMANTIC_TASKS = [
    "Скажи что-нибудь ласковое голосовым сообщением",
    "Запиши видео с комплиментом для партнера",
    "Спой куплет любимой песни голосовым сообщением"
]

# Настройки реферальной системы
REFERRAL_CODE_LENGTH = 8

# Настройки купонов
DEFAULT_COUPON_DISCOUNT = 20  # Процент скидки по умолчанию

# === Администраторы ===
ADMIN_IDS = [
    598785828,  # ID администратора
    # Добавьте других админов по необходимости
]

# Настройки платежных систем
PAYMENT_METHODS = {
    "stars": {
        "name": "Stars",
        "enabled": True,
        "api_key": "your_stars_api_key"  # Добавьте ваш API ключ Stars
    },
    "crypto": {
        "name": "CryptoBot",
        "enabled": True,
        "token": CRYPTO_BOT_TOKEN
    }
}

def generate_referral_code():
    """Генерирует уникальный реферальный код"""
    return secrets.token_hex(REFERRAL_CODE_LENGTH // 2).upper()

def generate_coupon_code():
    """Генерирует код купона"""
    return f"WETOGETHER{secrets.token_hex(4).upper()}"