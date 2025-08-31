# admin.py
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from database import get_db
from config import *
from states import Admin

# Список админов (замените на свои ID)
ADMIN_IDS = [598785828]  # ID администратора

async def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# === Админские команды ===
async def create_coupon(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    await message.answer("🎫 Создание нового купона\n\nВведите код купона:")
    await state.set_state(Admin.waiting_for_coupon_code)

async def process_coupon_code(message: Message, state: FSMContext):
    coupon_code = message.text.upper().strip()
    
    # Проверяем, что код не существует
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM coupons WHERE code = ?", (coupon_code,))
    if cur.fetchone():
        await message.answer("❌ Купон с таким кодом уже существует. Попробуйте другой код.")
        return
    
    await state.update_data(coupon_code=coupon_code)
    await message.answer("Введите процент скидки (например: 20):")
    await state.set_state(Admin.waiting_for_discount)

async def process_discount(message: Message, state: FSMContext):
    try:
        discount = int(message.text)
        if discount < 1 or discount > 100:
            await message.answer("❌ Процент скидки должен быть от 1 до 100.")
            return
    except ValueError:
        await message.answer("❌ Введите число.")
        return
    
    await state.update_data(discount=discount)
    await message.answer("Введите максимальное количество использований:")
    await state.set_state(Admin.waiting_for_max_uses)

async def process_max_uses(message: Message, state: FSMContext):
    try:
        max_uses = int(message.text)
        if max_uses < 1:
            await message.answer("❌ Количество использований должно быть больше 0.")
            return
    except ValueError:
        await message.answer("❌ Введите число.")
        return
    
    data = await state.get_data()
    coupon_code = data['coupon_code']
    discount = data['discount']
    
    # Создаем купон
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO coupons (code, discount_percent, max_uses)
        VALUES (?, ?, ?)
    """, (coupon_code, discount, max_uses))
    db.commit()
    
    await message.answer(f"✅ Купон создан!\n\n"
                        f"Код: {coupon_code}\n"
                        f"Скидка: {discount}%\n"
                        f"Максимум использований: {max_uses}")
    await state.clear()

async def list_coupons(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT code, discount_percent, max_uses, current_uses, is_active
        FROM coupons ORDER BY created_at DESC
    """)
    coupons = cur.fetchall()
    
    if not coupons:
        await message.answer("📋 Купоны не найдены.")
        return
    
    text = "📋 Список купонов:\n\n"
    for code, discount, max_uses, current_uses, is_active in coupons:
        status = "✅ Активен" if is_active else "❌ Неактивен"
        text += f"🎫 {code}\n"
        text += f"   Скидка: {discount}%\n"
        text += f"   Использований: {current_uses}/{max_uses}\n"
        text += f"   Статус: {status}\n\n"
    
    await message.answer(text)

async def deactivate_coupon(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    args = message.text.split()
    if len(args) != 2:
        await message.answer("❌ Использование: /deactivate_coupon КОД")
        return
    
    coupon_code = args[1].upper().strip()
    
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE coupons SET is_active = FALSE WHERE code = ?", (coupon_code,))
    
    if cur.rowcount > 0:
        await message.answer(f"✅ Купон {coupon_code} деактивирован.")
    else:
        await message.answer(f"❌ Купон {coupon_code} не найден.")

async def activate_coupon(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    args = message.text.split()
    if len(args) != 2:
        await message.answer("❌ Использование: /activate_coupon КОД")
        return
    
    coupon_code = args[1].upper().strip()
    
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE coupons SET is_active = TRUE WHERE code = ?", (coupon_code,))
    
    if cur.rowcount > 0:
        await message.answer(f"✅ Купон {coupon_code} активирован.")
    else:
        await message.answer(f"❌ Купон {coupon_code} не найден.")

async def stats(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    db = get_db()
    cur = db.cursor()
    
    # Статистика пользователей
    cur.execute("SELECT COUNT(*) FROM users WHERE is_deleted = FALSE")
    total_users = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM users WHERE is_deleted = FALSE AND referred_by IS NOT NULL")
    referred_users = cur.fetchone()[0]
    
    # Статистика матчей
    cur.execute("SELECT COUNT(*) FROM matches")
    total_matches = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM matches WHERE romantic_tour_paid = TRUE")
    romantic_tours = cur.fetchone()[0]
    
    # Статистика транзакций
    cur.execute("SELECT SUM(amount) FROM transactions WHERE type = 'payment' AND status = 'completed'")
    total_revenue = cur.fetchone()[0] or 0
    
    text = f"""📊 Статистика бота

👥 Пользователи:
   Всего: {total_users}
   По рефералам: {referred_users}

💕 Матчи:
   Всего: {total_matches}
   Романтических туров: {romantic_tours}

💰 Доходы:
   Общая выручка: ${total_revenue:.2f}"""
    
    await message.answer(text)

# Функция для регистрации админских команд
def register_admin_commands(dp: Dispatcher):
    dp.message.register(create_coupon, Command("create_coupon"))
    dp.message.register(process_coupon_code, StateFilter(Admin.waiting_for_coupon_code))
    dp.message.register(process_discount, StateFilter(Admin.waiting_for_discount))
    dp.message.register(process_max_uses, StateFilter(Admin.waiting_for_max_uses))
    dp.message.register(list_coupons, Command("list_coupons"))
    dp.message.register(deactivate_coupon, Command("deactivate_coupon"))
    dp.message.register(activate_coupon, Command("activate_coupon"))
    dp.message.register(stats, Command("stats"))

    # === Купоны пополнения баланса (номинал) ===
    dp.message.register(create_amount_coupon, Command("create_amount_coupon"))
    dp.message.register(process_amount_coupon_code, StateFilter(Admin.waiting_for_amount_coupon_code))
    dp.message.register(process_amount_value, StateFilter(Admin.waiting_for_amount_value))
    dp.message.register(process_amount_max_uses, StateFilter(Admin.waiting_for_amount_max_uses))

    # Быстрые команды
    dp.message.register(gen_amount_coupon_cmd, Command("gen_amount_coupon"))
    dp.message.register(list_amount_coupons, Command("list_amount_coupons"))


# ===== Купоны пополнения баланса (номинал) =====
async def create_amount_coupon(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    await message.answer("🎫 Создание купона-пополнения\n\nВведите код купона (A-Z/0-9):")
    await state.set_state(Admin.waiting_for_amount_coupon_code)

async def process_amount_coupon_code(message: Message, state: FSMContext):
    code = message.text.upper().strip()
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM balance_coupons WHERE code = ?", (code,))
    if cur.fetchone():
        await message.answer("❌ Купон с таким кодом уже существует. Попробуйте другой код.")
        return
    await state.update_data(amount_coupon_code=code)
    await message.answer("Введите сумму пополнения (например: 5.00):")
    await state.set_state(Admin.waiting_for_amount_value)

async def process_amount_value(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0.")
            return
    except ValueError:
        await message.answer("❌ Введите число, например 2 или 5.5")
        return
    await state.update_data(amount_value=amount)
    await message.answer("Введите максимальное число использований (по умолчанию 1):")
    await state.set_state(Admin.waiting_for_amount_max_uses)

async def process_amount_max_uses(message: Message, state: FSMContext):
    try:
        max_uses = int(message.text)
        if max_uses < 1:
            await message.answer("❌ Количество использований должно быть >= 1.")
            return
    except ValueError:
        await message.answer("❌ Введите целое число.")
        return
    data = await state.get_data()
    code = data['amount_coupon_code']
    amount = data['amount_value']
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        INSERT INTO balance_coupons (code, amount, max_uses)
        VALUES (?, ?, ?)
        """,
        (code, amount, max_uses),
    )
    db.commit()
    await message.answer(
        f"✅ Купон пополнения создан!\n\nКод: {code}\nСумма: ${amount:.2f}\nМакс. использований: {max_uses}"
    )
    await state.clear()

async def gen_amount_coupon_cmd(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    # Формат: /gen_amount_coupon CODE AMOUNT [MAX_USES]
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("❌ Использование: /gen_amount_coupon CODE AMOUNT [MAX_USES]\nНапример: /gen_amount_coupon LOVE5 5 1")
        return
    code = parts[1].upper().strip()
    if not code.isalnum():
        await message.answer("❌ Код должен содержать только буквы и цифры (A-Z, 0-9).")
        return
    try:
        amount = float(parts[2].replace(',', '.'))
    except ValueError:
        await message.answer("❌ AMOUNT должен быть числом. Пример: 5 или 2.5")
        return
    if amount <= 0:
        await message.answer("❌ Сумма должна быть больше 0.")
        return
    max_uses = 1
    if len(parts) >= 4:
        try:
            max_uses = int(parts[3])
        except ValueError:
            await message.answer("❌ MAX_USES должен быть целым числом.")
            return
        if max_uses < 1:
            await message.answer("❌ MAX_USES должен быть >= 1.")
            return
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute(
            """
            INSERT INTO balance_coupons (code, amount, max_uses)
            VALUES (?, ?, ?)
            """,
            (code, amount, max_uses),
        )
        db.commit()
    except Exception as e:
        await message.answer(f"❌ Ошибка создания: {e}")
        return
    await message.answer(f"✅ Купон создан!\nКод: {code}\nСумма: ${amount:.2f}\nМакс. использований: {max_uses}")

async def list_amount_coupons(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT code, amount, max_uses, current_uses, is_active, created_at
        FROM balance_coupons
        ORDER BY created_at DESC
        LIMIT 50
        """
    )
    rows = cur.fetchall()
    if not rows:
        await message.answer("📋 Купоны пополнения не найдены.")
        return
    text = "📋 Купоны пополнения (последние 50):\n\n"
    for code, amount, max_uses, current_uses, is_active, created_at in rows:
        status = "✅ Активен" if is_active else "❌ Неактивен"
        text += f"🎫 {code} — ${amount:.2f} — {current_uses}/{max_uses} — {status}\n"
    await message.answer(text)
