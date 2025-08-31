# main.py
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart, StateFilter
from database import get_db, init_db, create_active_chat
from aiogram.fsm.storage.base import StorageKey
from config import BOT_TOKEN, REGULAR_TASKS_COUNT, ROMANTIC_TASKS_COUNT, CRYPTO_BOT_TOKEN, REGULAR_TASKS, ROMANTIC_TASKS, ADMIN_IDS
from crypto_integration import CryptoBotIntegration
from utils import (
    apply_coupon, get_user_balance, get_user_stats, format_balance,
    get_user_referral_code, get_user_referral_stats, update_balance,
    create_payment_transaction
)
from coupon_system import CouponSystem

# === Инициализируем БД ===
init_db()

# === Бот ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# === CryptoBot интеграция ===
crypto_bot = CryptoBotIntegration(CRYPTO_BOT_TOKEN)

# === Система купонов ===
coupon_system = CouponSystem()

# === Состояния ===
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

class CryptoInput(StatesGroup):
    waiting_for_amount = State()

class TaskAnswer(StatesGroup):
    waiting_for_answer = State()

# === Клавиатуры ===
main_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔍 Найти пару")],
    [KeyboardButton(text="📝 Мои данные"), KeyboardButton(text="💰 Баланс")],
    [KeyboardButton(text="⭐ Премиум"), KeyboardButton(text="🎁 Рефералы")],
    [KeyboardButton(text="🗑️ Удалить")]
], resize_keyboard=True)

edit_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔄 Изменить данные")],
    [KeyboardButton(text="🔙 Назад")]
], resize_keyboard=True)

gender_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🙎 Мужской"), KeyboardButton(text="🙍 Женский")]
], resize_keyboard=True)

like_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❤️ Лайк", callback_data="like"),
     InlineKeyboardButton(text="❌ Пропустить", callback_data="dislike")]
])

# Кнопки после взаимного лайка
start_tasks_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎮 Начать задания", callback_data="start_tasks"),
     InlineKeyboardButton(text="❌ Игнорировать", callback_data="ignore_match")]
])

# Кнопки после завершения заданий
show_profile_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👤 Показать профиль", callback_data="show_profile")],
    [InlineKeyboardButton(text="💕 Платный тур ($2)", callback_data="buy_romantic_tour")]
])

# Клавиатура для романтического тура
romantic_tour_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💕 Романтический тур ($2)", callback_data="buy_romantic_tour")],
    [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
])

# Клавиатура для оплаты
payment_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="₿ Оплатить CryptoBot", callback_data="pay_crypto")],
    [InlineKeyboardButton(text="💰 Оплатить с баланса", callback_data="pay_balance")],
    [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
])

# === Проверка регистрации ===
def is_registered(user_id):
    db = None
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cur.fetchone() is not None
    except Exception as e:
        print(f"Error checking registration: {e}")
        return False
    finally:
        if db:
            try:
                db.close()
            except:
                pass

# === Команда /start ===
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    if is_registered(message.from_user.id):
        await message.answer("Привет! Ты уже зарегистрирован.", reply_markup=main_kb)
        return
    await message.answer("👋 Привет! Я помогу тебе найти пару через совместные задания.\n"
                         "Давай начнём с регистрации. Как тебя зовут?")
    await state.set_state(Registration.name)

# === Регистрация ===
@dp.message(Registration.name)
async def reg_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Теперь выбери свой пол:", reply_markup=gender_kb)
    await state.set_state(Registration.gender)

@dp.message(Registration.gender, F.text.in_(["🙎 Мужской", "🙍 Женский"]))
async def reg_gender(message: Message, state: FSMContext):
    gender = "male" if message.text == "🙎 Мужской" else "female"
    await state.update_data(gender=gender)
    await message.answer("Сколько тебе лет?")
    await state.set_state(Registration.age)

@dp.message(Registration.age)
async def reg_age(message: Message, state: FSMContext):
    try:
        age = int(message.text)
        await state.update_data(age=age)
        await message.answer("Из какого ты города?")
        await state.set_state(Registration.city)
    except ValueError:
        await message.answer("Введите возраст числом.")

@dp.message(Registration.city)
async def reg_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text.lower())
    await message.answer("Напиши немного о себе (интересы, цели знакомства).")
    await state.set_state(Registration.bio)

@dp.message(Registration.bio)
async def reg_bio(message: Message, state: FSMContext):
    await state.update_data(bio=message.text)
    await message.answer("Хочешь добавить фото? Отправь его сейчас.")
    await state.set_state(Registration.photo)

@dp.message(StateFilter(Registration.photo), F.photo)
async def reg_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    db = None
    try:
        db = get_db()
        cur = db.cursor()
        
        # Проверяем, есть ли сохраненный баланс
        cur.execute("SELECT balance FROM saved_balances WHERE user_id = ? ORDER BY saved_at DESC LIMIT 1", (message.from_user.id,))
        saved_balance_result = cur.fetchone()
        restored_balance = saved_balance_result[0] if saved_balance_result else 0.0
        
        # Создаем пользователя с восстановленным балансом
        cur.execute("""
            REPLACE INTO users (user_id, name, gender, age, city, bio, photo, balance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (message.from_user.id, data['name'], data['gender'], data['age'],
              data['city'], data['bio'], photo_id, restored_balance))
        
        # Если баланс был восстановлен, удаляем запись о сохранении
        if saved_balance_result:
            cur.execute("DELETE FROM saved_balances WHERE user_id = ?", (message.from_user.id,))
            
        db.commit()
        
        if restored_balance > 0:
            await message.answer(
                f"✅ Анкета обновлена!\n\n"
                f"💰 Ваш баланс ${restored_balance:.2f} восстановлен!",
                reply_markup=main_kb
            )
        else:
        await message.answer("✅ Анкета обновлена!", reply_markup=main_kb)
            
        await state.clear()
    except Exception as e:
        print(f"Error saving photo: {e}")
        await message.answer("❌ Ошибка сохранения фото. Попробуйте еще раз.")
    finally:
        if db:
            try:
                db.close()
            except:
                pass

@dp.message(StateFilter(Registration.photo))
async def skip_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    db = None
    try:
        db = get_db()
        cur = db.cursor()
        
        # Проверяем, есть ли сохраненный баланс
        cur.execute("SELECT balance FROM saved_balances WHERE user_id = ? ORDER BY saved_at DESC LIMIT 1", (message.from_user.id,))
        saved_balance_result = cur.fetchone()
        restored_balance = saved_balance_result[0] if saved_balance_result else 0.0
        
        # Создаем пользователя с восстановленным балансом
        cur.execute("""
            REPLACE INTO users (user_id, name, gender, age, city, bio, balance)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (message.from_user.id, data['name'], data['gender'], data['age'],
              data['city'], data['bio'], restored_balance))
        
        # Если баланс был восстановлен, удаляем запись о сохранении
        if saved_balance_result:
            cur.execute("DELETE FROM saved_balances WHERE user_id = ?", (message.from_user.id,))
            
        db.commit()
        
        if restored_balance > 0:
            await message.answer(
                f"✅ Анкета обновлена!\n\n"
                f"💰 Ваш баланс ${restored_balance:.2f} восстановлен!",
                reply_markup=main_kb
            )
        else:
        await message.answer("✅ Анкета обновлена!", reply_markup=main_kb)
            
        await state.clear()
    except Exception as e:
        print(f"Error saving profile: {e}")
        await message.answer("❌ Ошибка сохранения профиля. Попробуйте еще раз.")
    finally:
        if db:
            try:
                db.close()
            except:
                pass

# === Поиск пары ===
@dp.message(F.text == "🔍 Найти пару")
async def ask_city_for_search(message: Message, state: FSMContext):
    await message.answer("Из какого города ты хочешь найти пару?")
    await state.set_state(Search.city)

@dp.message(Search.city)
async def ask_age_range(message: Message, state: FSMContext):
    await state.update_data(city=message.text.lower())
    await message.answer("Какой возрастной диапазон тебя интересует? Например: 18-30")
    await state.set_state(Search.age_range)

@dp.message(Search.age_range)
async def start_search_with_filters(message: Message, state: FSMContext):
    # Обычный поиск анкет
    try:
        min_age, max_age = map(int, message.text.strip().split('-'))
        data = await state.get_data()
        city_preference = data['city']
        user_id = message.from_user.id

        db = None
        try:
            db = get_db()
            cur = db.cursor()
            cur.execute("SELECT gender FROM users WHERE user_id = ?", (user_id,))
            result = cur.fetchone()
            if not result:
                await message.answer("Сначала зарегистрируйся.")
                await state.clear()
                return

            my_gender = result[0]
            target_gender = "female" if my_gender == "male" else "male"

            # Ищем анкеты
            cur.execute("""
                SELECT u.* FROM users u
                WHERE u.gender = ?
                  AND LOWER(u.city) = LOWER(?)
                  AND u.age BETWEEN ? AND ?
                  AND u.user_id != ?
                  AND u.is_deleted = FALSE
                ORDER BY RANDOM() LIMIT 1
            """, (target_gender, city_preference, min_age, max_age, user_id))

            profile = cur.fetchone()
            if not profile:
                await message.answer(f"Анкеты закончились :(\n\nПоиск: {target_gender} в '{city_preference}' {min_age}-{max_age}")
                await state.clear()
                return

            user_data = {
                "user_id": profile[0],
                "name": profile[1],
                "gender": profile[2],
                "age": profile[3],
                "city": profile[4],
                "bio": profile[5],
                "photo": profile[6]
            }

            text = f"""
👤 {user_data['name']}, {user_data['age']}
📍 {user_data['city']}
📝 {user_data['bio']}
"""

            await state.update_data(current_profile_id=user_data['user_id'])

            if user_data['photo']:
                await bot.send_photo(
                    chat_id=message.chat.id,
                    photo=user_data['photo'],
                    caption=text,
                    reply_markup=like_kb
                )
            else:
                await message.answer(text, reply_markup=like_kb)

        except Exception as e:
            print(f"❌ SEARCH ERROR: {e}")
            await message.answer("Произошла ошибка при поиске.")
            await state.clear()
        finally:
            if db:
                try:
                    db.close()
                except:
                    pass

    except ValueError:
        await message.answer("Ошибка в формате возраста. Пример: 18-30")
        await state.clear()

# === Лайки и взаимные симпатии ===
@dp.callback_query(F.data == "like")
async def handle_like(callback_query, state: FSMContext):
    user_id = callback_query.from_user.id
    data = await state.get_data()
    liked_id = data.get('current_profile_id')

    if not liked_id:
        await callback_query.answer("Не могу определить анкету.")
        return

    db = None
    try:
        db = get_db()
        cur = db.cursor()

        # Удаляем старые матчи и прогресс между этими пользователями
        cur.execute("DELETE FROM matches WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)", 
                   (user_id, liked_id, liked_id, user_id))
        cur.execute("DELETE FROM match_tasks WHERE match_id IN (SELECT id FROM matches WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?))", 
                   (user_id, liked_id, liked_id, user_id))

        # Ставим лайк (соответствие схеме: user_id, liked_id)
        cur.execute("INSERT OR IGNORE INTO likes (user_id, liked_id) VALUES (?, ?)", (user_id, liked_id))
        db.commit()

        # Проверяем, есть ли взаимный лайк (liked_id уже лайкал user_id)
        cur.execute("SELECT 1 FROM likes WHERE user_id = ? AND liked_id = ?", (liked_id, user_id))
        mutual = cur.fetchone() is not None

        if mutual:
            # Создаем новый матч
            cur.execute("INSERT INTO matches (user1_id, user2_id, tasks_completed, romantic_tasks_completed) VALUES (?, ?, 0, 0)", (user_id, liked_id))
            db.commit()
            match_id = cur.lastrowid

            # Уведомляем обоих о взаимной симпатии и предлагаем начать задания
            await bot.send_message(user_id, "💕 У вас взаимная симпатия!", reply_markup=start_tasks_kb)
            await bot.send_message(liked_id, "💕 У вас взаимная симпатия!", reply_markup=start_tasks_kb)
        else:
            # Отправляем профиль лайкнувшего пользователю, чтобы он мог ответить лайком
            cur.execute("SELECT name, age, city, bio, photo FROM users WHERE user_id = ?", (user_id,))
            liker = cur.fetchone()
            if liker:
                liker_name, liker_age, liker_city, liker_bio, liker_photo = liker
                text = f"""
👤 {liker_name}, {liker_age}
📍 {liker_city}
📝 {liker_bio}
"""
                # Устанавливаем контекст состояния для liked_id, чтобы коллбэк 'like' знал текущий профиль
                try:
                    liked_state_context = FSMContext(storage=dp.storage, key=StorageKey(chat_id=liked_id, user_id=liked_id, bot_id=bot.id))
                    await liked_state_context.update_data(current_profile_id=user_id)
                except Exception as e:
                    print(f"Ошибка установки состояния для ответа на лайк: {e}")

                try:
                    if liker_photo:
                        await bot.send_photo(chat_id=liked_id, photo=liker_photo, caption=text, reply_markup=like_kb)
                    else:
                        await bot.send_message(chat_id=liked_id, text=text, reply_markup=like_kb)
                except Exception as e:
                    print(f"Ошибка отправки профиля для ответа на лайк: {e}")
            else:
                try:
                    await bot.send_message(liked_id, "💘 Кто-то поставил вам лайк! Зайдите в поиск, чтобы ответить.")
                except:
                    pass

        await callback_query.message.delete()
        await callback_query.answer()
        await state.clear()
        
    except Exception as e:
        print(f"Error handling like: {e}")
        await callback_query.answer("Ошибка при обработке лайка.")
    finally:
        if db:
            try:
                db.close()
            except:
                pass

@dp.callback_query(F.data == "dislike")
async def handle_dislike(callback_query, state: FSMContext):
    await callback_query.message.delete()
    await callback_query.answer()
    await state.clear()

# === Автоматическое начало первого задания ===
async def start_first_task(match_id: int, user1_id: int, user2_id: int):
    """Автоматически начинает первое задание для обоих участников"""
    try:
        # Получаем первое задание
        task_text = REGULAR_TASKS[0]
        
        # Отправляем задание обоим участникам
        text = f"🎯 Первое задание:\n\n{task_text}"
        
        try:
            await bot.send_message(user1_id, text)
        except:
            pass
        try:
            await bot.send_message(user2_id, text)
        except:
            pass
        
        # Устанавливаем состояние для ожидания ответа ОБОИХ участников
        try:
            user1_state_context = FSMContext(storage=dp.storage, key=StorageKey(chat_id=user1_id, user_id=user1_id, bot_id=bot.id))
            user2_state_context = FSMContext(storage=dp.storage, key=StorageKey(chat_id=user2_id, user_id=user2_id, bot_id=bot.id))
        except Exception as e:
            print(f"Ошибка создания состояния: {e}")
            return
        
        await user1_state_context.set_state(TaskAnswer.waiting_for_answer)
        await user1_state_context.update_data(match_id=match_id, task_index=0, is_romantic=False, partner_id=user2_id)
        
        await user2_state_context.set_state(TaskAnswer.waiting_for_answer)
        await user2_state_context.update_data(match_id=match_id, task_index=0, is_romantic=False, partner_id=user1_id)
        
        print(f"✅ DEBUG: Первое задание автоматически начато для матча {match_id}")
        
    except Exception as e:
        print(f"❌ DEBUG: Ошибка при автоматическом начале заданий: {e}")

# === Обработка ответов на задания ===
@dp.message(StateFilter(TaskAnswer.waiting_for_answer))
async def process_task_answer(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    match_id = data.get('match_id')
    task_index = data.get('task_index')
    is_romantic = data.get('is_romantic', False)
    
    print(f"🔍 DEBUG: Обрабатываем ответ пользователя {user_id}")
    print(f"🔍 DEBUG: match_id: {match_id}, task_index: {task_index}, is_romantic: {is_romantic}")
    print(f"🔍 DEBUG: Данные состояния: {data}")

    if not match_id:
        await message.answer("Ошибка: матч не найден в состоянии.")
        await state.clear()
        return

    db = None
    try:
        db = get_db()
        cur = db.cursor()

        # Получаем информацию о матче
        cur.execute("SELECT user1_id, user2_id, tasks_completed, romantic_tasks_completed FROM matches WHERE id = ?", (match_id,))
        match_data = cur.fetchone()
        if not match_data:
            await message.answer("Ошибка: матч не найден.")
            await state.clear()
            return
        
        user1_id, user2_id, tasks_completed, romantic_tasks_completed = match_data
        # Используем partner_id из состояния, если есть, иначе вычисляем
        partner_id = data.get('partner_id')
        if not partner_id:
            partner_id = user1_id if user_id == user2_id else user2_id

        # Определяем тип ответа
        print(f"🔍 DEBUG: Тип сообщения: {type(message)}")
        print(f"🔍 DEBUG: Есть ли текст: {hasattr(message, 'text') and message.text}")
        print(f"🔍 DEBUG: Есть ли голос: {hasattr(message, 'voice') and message.voice}")
        print(f"🔍 DEBUG: Есть ли видео: {hasattr(message, 'video') and message.video}")
        
        if is_romantic:
            print(f"🔍 DEBUG: Обрабатываем романтическое задание для пользователя {user_id}")
            if getattr(message, 'voice', None):
                answer_content = message.voice.file_id
                answer_type = "voice"
                print(f"✅ DEBUG: Получено голосовое сообщение для романтического задания")
            elif getattr(message, 'video', None):
                answer_content = message.video.file_id
                answer_type = "video"
                print(f"✅ DEBUG: Получено видео сообщение для романтического задания")
            elif getattr(message, 'audio', None):
                # На случай если пользователь отправляет аудио вместо voice
                answer_content = message.audio.file_id
                answer_type = "audio"
                print(f"✅ DEBUG: Получено аудио сообщение для романтического задания")
            else:
                print(f"❌ DEBUG: Неверный тип сообщения для романтического задания: {type(message)}")
                await message.answer("Для романтических заданий нужно отправить голосовое, аудио или видео сообщение!")
                return
        else:
            if message.text:
                answer_content = message.text.strip()
                answer_type = "text"
            else:
                await message.answer("Пожалуйста, отправьте текстовый ответ на задание.")
                return

        # Сохраняем ответ пользователя (обновляем если уже есть)
        cur.execute("""
            INSERT OR REPLACE INTO match_tasks (match_id, task_index, user_id, answer, answer_type)
            VALUES (?, ?, ?, ?, ?)
        """, (match_id, task_index, user_id, answer_content, answer_type))
        db.commit()

        # Отправляем ответ партнеру
        try:
            if answer_type == "text":
                await bot.send_message(partner_id, f"🎯 Ваш партнер ответил на задание {task_index + 1}:\n\n{answer_content}")
                print(f"✅ DEBUG: Текстовый ответ переслан партнеру {partner_id}")
            elif answer_type == "voice":
                await bot.send_voice(partner_id, voice=answer_content, caption=f"🎤 Ваш партнер ответил на задание {task_index + 1}!")
                print(f"✅ DEBUG: Голосовое сообщение переслано партнеру {partner_id}")
            elif answer_type == "video":
                await bot.send_video(partner_id, video=answer_content, caption=f"🎥 Ваш партнер ответил на задание {task_index + 1}!")
                print(f"✅ DEBUG: Видео сообщение переслано партнеру {partner_id}")
            elif answer_type == "audio":
                await bot.send_audio(partner_id, audio=answer_content, caption=f"🎵 Ваш партнер ответил на задание {task_index + 1}!")
                print(f"✅ DEBUG: Аудио сообщение переслано партнеру {partner_id}")
        except Exception as e:
            print(f"❌ DEBUG: Ошибка при отправке ответа партнеру: {e}")
            await message.answer("Произошла ошибка при отправке вашего ответа партнеру.")

        # Проверяем, ответили ли оба участника (считаем уникальных пользователей на этом задании)
        cur.execute("SELECT COUNT(DISTINCT user_id) FROM match_tasks WHERE match_id = ? AND task_index = ?", (match_id, task_index))
        answers_count = cur.fetchone()[0]

        if answers_count >= 2:
            # Оба участника ответили - переходим к следующему заданию
            await message.answer("🎉 Оба участника ответили на задание! Переходим к следующему...")
            await bot.send_message(partner_id, "🎉 Оба участника ответили на задание! Переходим к следующему...")

            # Обновляем прогресс
            if is_romantic:
                cur.execute("UPDATE matches SET romantic_tasks_completed = romantic_tasks_completed + 1 WHERE id = ?", (match_id,))
            else:
                cur.execute("UPDATE matches SET tasks_completed = tasks_completed + 1 WHERE id = ?", (match_id,))
            db.commit()

            # Очищаем состояние для обоих пользователей ТОЛЬКО после обновления прогресса
            try:
                user1_state_context = FSMContext(storage=dp.storage, key=StorageKey(chat_id=user1_id, user_id=user1_id, bot_id=bot.id))
                user2_state_context = FSMContext(storage=dp.storage, key=StorageKey(chat_id=user2_id, user_id=user2_id, bot_id=bot.id))
                
                await user1_state_context.clear()
                await user2_state_context.clear()
            except Exception as e:
                print(f"Ошибка очистки состояния: {e}")

            # Автоматически показываем следующее задание или завершаем
            await show_next_task_or_finish(match_id, user1_id, user2_id, is_romantic)
        else:
            # Только один участник ответил - ждем второго
            await message.answer("✅ Ваш ответ отправлен партнеру! Ожидаем его ответа.")

    except Exception as e:
        print(f"❌ DEBUG: Ошибка при обработке ответа: {e}")
        await message.answer("Произошла ошибка при обработке вашего ответа.")
    finally:
        if db:
            try:
                db.close()
            except:
                pass

# === Автоматическое показ следующего задания или завершение ===
async def show_next_task_or_finish(match_id: int, user1_id: int, user2_id: int, is_romantic: bool):
    """Автоматически показывает следующее задание или завершает матч"""
    db = None
    try:
        db = get_db()
        cur = db.cursor()
        
        if is_romantic:
            # Проверяем прогресс романтических заданий
            cur.execute("SELECT romantic_tasks_completed FROM matches WHERE id = ?", (match_id,))
            result = cur.fetchone()
            if not result:
                return
            
            progress = result[0]
            
            if progress >= ROMANTIC_TASKS_COUNT:
                # Все романтические задания выполнены
                text = "🎉 Вы выполнили все романтические задания!\n\nТеперь вы можете общаться напрямую."
                try:
                    await bot.send_message(user1_id, text, reply_markup=show_profile_kb)
                except:
                    pass
                try:
                    await bot.send_message(user2_id, text, reply_markup=show_profile_kb)
                except:
                    pass
                
                # Делаем матч неактивным
                cur.execute("UPDATE matches SET active = FALSE WHERE id = ?", (match_id,))
                db.commit()
            else:
                # Показываем следующее романтическое задание
                task_text = ROMANTIC_TASKS[progress]
                text = f"💕 Романтическое задание {progress + 1}:\n\n{task_text}"
                
                # Устанавливаем состояние для ОБОИХ участников
                try:
                    user1_state_context = FSMContext(storage=dp.storage, key=StorageKey(chat_id=user1_id, user_id=user1_id, bot_id=bot.id))
                    user2_state_context = FSMContext(storage=dp.storage, key=StorageKey(chat_id=user2_id, user_id=user2_id, bot_id=bot.id))
                except Exception as e:
                    print(f"Ошибка создания состояния: {e}")
                    return
                
                await user1_state_context.set_state(TaskAnswer.waiting_for_answer)
                await user1_state_context.update_data(match_id=match_id, task_index=progress, is_romantic=True, partner_id=user2_id)
                
                await user2_state_context.set_state(TaskAnswer.waiting_for_answer)
                await user2_state_context.update_data(match_id=match_id, task_index=progress, is_romantic=True, partner_id=user1_id)
                
                print(f"✅ DEBUG: Романтическое задание {progress + 1} установлено для матча {match_id} у ОБОИХ пользователей")
                
                try:
                    await bot.send_message(user1_id, text)
                except:
                    pass
                try:
                    await bot.send_message(user2_id, text)
                except:
                    pass
        else:
            # Проверяем прогресс обычных заданий
            cur.execute("SELECT tasks_completed FROM matches WHERE id = ?", (match_id,))
            result = cur.fetchone()
            if not result:
                return
            
            tasks_completed = result[0]
            
            if tasks_completed >= REGULAR_TASKS_COUNT:
                # Все обычные задания выполнены
                # Проверяем, оплачен ли романтический тур
                cur.execute("SELECT romantic_tour_paid FROM matches WHERE id = ?", (match_id,))
                romantic_tour_paid = cur.fetchone()[0]
                
                if romantic_tour_paid:
                    # Автоматически начинаем романтический тур
                    await start_romantic_tour(match_id, user1_id, user2_id)
                else:
                    # Показываем кнопку "Показать профиль" ОБЯЗАТЕЛЬНО
                    text = "🎉 Вы выполнили все задания!\n\nТеперь вы можете увидеть профиль друг друга."
                    try:
                        await bot.send_message(user1_id, text, reply_markup=show_profile_kb)
                    except:
                        pass
                    try:
                        await bot.send_message(user2_id, text, reply_markup=show_profile_kb)
                    except:
                        pass
                    
                    # Делаем матч неактивным только если романтический тур не оплачен
                    cur.execute("UPDATE matches SET active = FALSE WHERE id = ?", (match_id,))
                    db.commit()
            else:
                # Показываем следующее обычное задание
                task_text = REGULAR_TASKS[tasks_completed]
                text = f"🎯 Задание {tasks_completed + 1}:\n\n{task_text}"
                
                # Устанавливаем состояние для обоих участников
                try:
                    user1_state_context = FSMContext(storage=dp.storage, key=StorageKey(chat_id=user1_id, user_id=user1_id, bot_id=bot.id))
                    user2_state_context = FSMContext(storage=dp.storage, key=StorageKey(chat_id=user2_id, user_id=user2_id, bot_id=bot.id))
                except Exception as e:
                    print(f"Ошибка создания состояния: {e}")
                    return
                
                await user1_state_context.set_state(TaskAnswer.waiting_for_answer)
                await user1_state_context.update_data(match_id=match_id, task_index=tasks_completed, is_romantic=False, partner_id=user2_id)
                
                await user2_state_context.set_state(TaskAnswer.waiting_for_answer)
                await user2_state_context.update_data(match_id=match_id, task_index=tasks_completed, is_romantic=False, partner_id=user1_id)
                
                print(f"✅ DEBUG: Обычное задание {tasks_completed + 1} установлено для матча {match_id}")
                
                try:
                    await bot.send_message(user1_id, text)
                except:
                    pass
                try:
                    await bot.send_message(user2_id, text)
                except:
                    pass
                
    except Exception as e:
        print(f"❌ DEBUG: Ошибка при показе следующего задания: {e}")
    finally:
        if db:
            try:
                db.close()
            except:
                pass

# === Показать профиль партнера ===
@dp.callback_query(F.data == "show_profile")
async def show_partner_profile(callback_query):
    user_id = callback_query.from_user.id
    db = None
    try:
        db = get_db()
        cur = db.cursor()
        
        # Находим матч пользователя - ищем по последнему завершенному матчу
        cur.execute("""
            SELECT user1_id, user2_id 
            FROM matches 
            WHERE (user1_id = ? OR user2_id = ?) 
              AND active = FALSE 
              AND (tasks_completed >= 5 OR romantic_tasks_completed >= 3)
            ORDER BY id DESC 
            LIMIT 1
        """, (user_id, user_id))
        match = cur.fetchone()
        if not match:
            await callback_query.answer("Матч не найден.")
            return
        
        user1_id, user2_id = match
        partner_id = user1_id if user_id == user2_id else user2_id
        
        # Получаем профиль партнера
        cur.execute("SELECT name FROM users WHERE user_id = ?", (partner_id,))
        partner_profile = cur.fetchone()
        if not partner_profile:
            await callback_query.answer("Профиль партнера не найден.")
            return
        
        partner_name = partner_profile[0]
        
        # Получаем username из Telegram API
        try:
            partner_user = await bot.get_chat(partner_id)
            partner_username = partner_user.username
        except:
            partner_username = None
        
        text = f"👤 Профиль партнера:\n\n"
        text += f"Имя: {partner_name}\n"
        if partner_username:
            text += f"Username: @{partner_username}\n"
        else:
            text += "Username: не указан"
        
        await callback_query.message.edit_text(text)
        await callback_query.answer()
        
    except Exception as e:
        print(f"Error showing partner profile: {e}")
        await callback_query.answer("Ошибка при показе профиля.")
    finally:
        if db:
            try:
                db.close()
            except:
                pass

# === Мои данные ===
@dp.message(F.text == "📝 Мои данные")
async def show_my_profile(message: Message):
    user_id = message.from_user.id
    db = None
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        profile = cur.fetchone()
        if not profile:
            await message.answer("Вы ещё не зарегистрированы.")
            return
        
        # Проверяем премиум статус
        balance = get_user_balance(user_id)
        
        # Определяем премиум статус
        premium_status = ""
        if balance >= 10:
            premium_status = "👑 ПРЕМИУМ"
        elif balance >= 5:
            premium_status = "⭐ ПРО"
        elif balance >= 2:
            premium_status = "💎 VIP"
        
        # Получаем статистику
        stats = get_user_stats(user_id)
        
        text = f"""
👤 {profile[1]}, {profile[3]} {premium_status}
📍 {profile[4]}
📝 {profile[5]}
💰 Баланс: ${balance:.2f}

📊 Статистика:
❤️ Получено лайков: {stats['likes_received']}
💝 Поставлено лайков: {stats['likes_given']}
💕 Матчей: {stats['matches_count']}
👥 Рефералов: {stats['referrals_count']}

🎯 Уровень: {'🔥 Высокий' if stats['likes_received'] > 10 else '⭐ Средний' if stats['likes_received'] > 5 else '🌱 Начинающий'}
"""
        if profile[6]:
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=profile[6],
                caption=text,
                reply_markup=edit_kb
            )
        else:
            await message.answer(text, reply_markup=edit_kb)
            
    except Exception as e:
        print(f"Error showing profile: {e}")
        await message.answer("❌ Ошибка загрузки профиля. Попробуйте еще раз.")
    finally:
        if db:
            try:
                db.close()
            except:
                pass

@dp.message(F.text == "🔄 Изменить данные")
async def start_edit_profile(message: Message, state: FSMContext):
    await message.answer("Давай обновим твою анкету. Как тебя зовут?")
    await state.set_state(Registration.name)

@dp.message(F.text == "🔙 Назад")
async def go_back(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Вы вернулись в главное меню", reply_markup=main_kb)

# === Баланс ===
@dp.message(F.text == "💰 Баланс")
async def show_balance(message: Message):
    user_id = message.from_user.id
    balance = get_user_balance(user_id)
    
    text = f"""💰 Ваш баланс: {format_balance(balance)}

💳 Пополнить баланс можно через:
• CryptoBot
• Реферальные бонусы
• Купоны

⭐ Супер-лайк: $1
🚀 Буст профиля: $3
💕 Романтический тур: $2 (после 5 заданий)"""
    
    balance_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="₿ Пополнить CryptoBot", callback_data="topup_crypto")],
        [InlineKeyboardButton(text="🎫 Использовать купон", callback_data="use_balance_coupon")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    
    await message.answer(text, reply_markup=balance_kb)

# === Премиум функции ===
@dp.message(F.text == "⭐ Премиум")
async def show_premium(message: Message):
    text = """⭐ Премиум функции

⭐ Супер-лайк - $1
• Показывает вашу анкету в топе
• Больше шансов на взаимность

🚀 Буст профиля - $3
• Показывает вашу анкету чаще
• Приоритет в поиске

💡 Романтический тур ($2) будет доступен после прохождения 5 заданий и позволит вам получить доступ к специальным голосовым романтическим заданиям."""
    
    premium_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💕 Романтический тур ($2)", callback_data="romantic_tour")],
        [InlineKeyboardButton(text="⭐ Супер-лайк ($1)", callback_data="buy_super_like")],
        [InlineKeyboardButton(text="🚀 Буст профиля ($3)", callback_data="buy_boost")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    
    await message.answer(text, reply_markup=premium_kb)

# === Реферальная система ===
@dp.message(F.text == "🎁 Рефералы")
async def show_referral(message: Message):
    user_id = message.from_user.id
    referral_code = get_user_referral_code(user_id)
    stats = get_user_referral_stats(user_id)
    
    text = f"""🎁 Реферальная система

🔗 Ваша реферальная ссылка:
https://t.me/WeTogetherBot?start={referral_code}

💰 За каждого приглашенного друга: $1
👥 Приглашено друзей: {stats['referrals_count']}
💵 Заработано: ${stats['total_earned']:.2f}

📱 Поделитесь ссылкой с друзьями!

💡 Для получения реферального бонуса ваш друг должен зарегистрироваться по этой ссылке"""
    
    await message.answer(text)

# === Удаление анкеты ===
@dp.message(F.text == "🗑️ Удалить")
async def delete_profile(message: Message):
    text = """🗑️ Удаление анкеты

⚠️ Внимание! Это действие нельзя отменить.

После удаления:
• Ваша анкета исчезнет из поиска
• Все матчи будут удалены
• Баланс будет обнулен
• История будет потеряна

Вы уверены, что хотите удалить анкету?"""
    
    delete_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete")],
        [InlineKeyboardButton(text="🗑️ Да, удалить", callback_data="confirm_delete")]
    ])
    
    await message.answer(text, reply_markup=delete_kb)

# === Команда для купонов ===
@dp.message(lambda msg: msg.text and msg.text.startswith('/coupon'))
async def use_coupon_command(message: Message):
    try:
        coupon_code = message.text.split()[1].upper()
        user_id = str(message.from_user.id)
        
        # Используем новую систему купонов
        coupon = coupon_system.get_coupon(coupon_code)
        
        if not coupon:
            await message.answer("❌ Купон не найден.")
            return
        
        if coupon["is_used"]:
            await message.answer("❌ Этот купон уже использован.")
            return
        
        # Проверяем срок действия
        from datetime import datetime
        expiry_date = datetime.fromisoformat(coupon["expires_at"])
        if datetime.now() > expiry_date:
            await message.answer("❌ Срок действия купона истек.")
            return
        
        # Используем купон
        if coupon_system.use_coupon(coupon_code, user_id):
            # Пополняем баланс пользователя
            amount_rub = coupon['amount']
            amount_usd = amount_rub / 100  # Примерный курс 1 USD = 100 RUB
            
            # Обновляем баланс в базе данных
            db = None
            try:
                db = get_db()
                cur = db.cursor()
                
                # Получаем текущий баланс
                cur.execute("SELECT balance FROM users WHERE user_id = ?", (message.from_user.id,))
                result = cur.fetchone()
                
                if result:
                    current_balance = result[0]
                    new_balance = current_balance + amount_usd
                    
                    # Обновляем баланс
                    cur.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, message.from_user.id))
                    
                    # Создаем транзакцию
                    cur.execute("""
                        INSERT INTO transactions (user_id, amount, type, description, status)
                        VALUES (?, ?, 'coupon', 'Coupon redemption', 'completed')
                    """, (message.from_user.id, amount_usd))
                    
                    db.commit()
                    
                    response = (
                        f"✅ Купон успешно использован!\n\n"
                        f"💰 Пополнено: ${amount_usd:.2f} ({amount_rub} руб.)\n"
                        f"🔑 Код: {coupon_code}\n"
                        f"📅 Использован: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                        f"💳 Новый баланс: ${new_balance:.2f}"
                    )
                    await message.answer(response, reply_markup=main_kb)
        else:
                    await message.answer("❌ Пользователь не найден в базе данных.")
                    
            except Exception as e:
                print(f"Error updating balance: {e}")
                if db:
                    try:
                        db.rollback()
                    except:
                        pass
                await message.answer("❌ Ошибка при пополнении баланса.")
            finally:
                if db:
                    try:
                        db.close()
                    except:
                        pass
        else:
            await message.answer("❌ Ошибка при использовании купона.")
            
    except IndexError:
        await message.answer("❌ Неверный формат. Используйте: /coupon КОД_КУПОНА")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
        print(f"Coupon error: {e}")

# === Команда для создания купонов (только для админов) ===
@dp.message(lambda msg: msg.text and msg.text.startswith('/create_cupone'))
async def create_coupon_command(message: Message):
    """Команда для создания купона (только для админов)"""
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь админом
    if user_id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для создания купонов.")
        return
    
    # Парсим аргументы команды
    args = message.text.split()[1:]
    
    if len(args) != 2:
        await message.answer(
            "❌ Неверный формат команды!\n\n"
            "Использование: /create_cupone <сумма> <дни>\n"
            "Пример: /create_cupone 100 30\n\n"
            "💰 Сумма - номинал купона в рублях\n"
            "⏰ Дни - количество дней действия купона"
        )
        return
    
    try:
        amount = float(args[0])
        days = int(args[1])
        
        if amount <= 0 or days <= 0:
            await message.answer("❌ Сумма и количество дней должны быть положительными числами.")
            return
        
        # Создаем купон
        coupon = coupon_system.create_coupon(
            amount=amount,
            days_valid=days,
            created_by=str(user_id)
        )
        
        # Отправляем информацию о созданном купоне
        response = (
            f"✅ Купон создан успешно!\n\n"
            f"🔑 Код: `{coupon['code']}`\n"
            f"💰 Сумма: {amount} руб.\n"
            f"📅 Действует до: {coupon['expires_at'][:10]}\n"
            f"⏰ Срок действия: {days} дней\n\n"
            f"💡 Пользователи могут использовать купон командой:\n"
            f"`/coupon {coupon['code']}`"
        )
        
        await message.answer(response, parse_mode='Markdown')
        
    except ValueError:
        await message.answer("❌ Ошибка: сумма и количество дней должны быть числами.")
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при создании купона: {str(e)}")

# === Команда для использования купона ===
@dp.message(lambda msg: msg.text and msg.text.startswith('/use_coupon'))
async def use_coupon_new_command(message: Message):
    """Команда для использования купона (новая система)"""
    args = message.text.split()[1:]
    
    if len(args) != 1:
        await message.answer("❌ Неверный формат. Используйте: /use_coupon <код>")
        return
    
    coupon_code = args[0].upper()
    user_id = str(message.from_user.id)
    
    # Получаем купон
    coupon = coupon_system.get_coupon(coupon_code)
    
    if not coupon:
        await message.answer("❌ Купон не найден.")
        return
    
    if coupon["is_used"]:
        await message.answer("❌ Этот купон уже использован.")
        return
    
    # Проверяем срок действия
    from datetime import datetime
    expiry_date = datetime.fromisoformat(coupon["expires_at"])
    if datetime.now() > expiry_date:
        await message.answer("❌ Срок действия купона истек.")
        return
    
    # Используем купон
    if coupon_system.use_coupon(coupon_code, user_id):
        # Здесь можно добавить логику начисления средств пользователю
        # Например, пополнение баланса или скидка на услуги
        
        response = (
            f"✅ Купон успешно использован!\n\n"
            f"💰 Сумма: {coupon['amount']} руб.\n"
            f"🔑 Код: {coupon_code}\n"
            f"📅 Использован: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"💡 Обратитесь к администратору для получения бонуса!"
        )
        await message.answer(response)
    else:
        await message.answer("❌ Ошибка при использовании купона.")

# === Команда для просмотра активных купонов (только для админов) ===
@dp.message(lambda msg: msg.text and msg.text.startswith('/active_coupons'))
async def active_coupons_command(message: Message):
    """Показывает все активные купоны (только для админов)"""
    user_id = message.from_user.id
    
    # Проверяем права админа
    if user_id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для просмотра купонов.")
        return
    
    active_coupons = coupon_system.get_active_coupons()
    
    if not active_coupons:
        await message.answer("📝 Активных купонов нет.")
        return
    
    response = "📝 Активные купоны:\n\n"
    
    for coupon in active_coupons:
        response += (
            f"🔑 Код: `{coupon['code']}`\n"
            f"💰 Сумма: {coupon['amount']} руб.\n"
            f"📅 Действует до: {coupon['expires_at'][:10]}\n"
            f"👤 Создан: {coupon['created_by']}\n"
            f"---\n"
        )
    
    await message.answer(response, parse_mode='Markdown')

# === Команда для удаления купона (только для админов) ===
@dp.message(lambda msg: msg.text and msg.text.startswith('/delete_coupon'))
async def delete_coupon_command(message: Message):
    """Удаляет купон (только для админов)"""
    user_id = message.from_user.id
    
    # Проверяем права админа
    if user_id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для удаления купонов.")
        return
    
    args = message.text.split()[1:]
    
    if len(args) != 1:
        await message.answer("❌ Неверный формат. Используйте: /delete_coupon <код>")
        return
    
    coupon_code = args[0].upper()
    
    # Удаляем купон
    if coupon_system.delete_coupon(coupon_code, str(user_id)):
        await message.answer(f"✅ Купон {coupon_code} успешно удален.")
    else:
        await message.answer(f"❌ Ошибка при удалении купона {coupon_code}.")

# === Команда для просмотра статистики бота (только для админов) ===
@dp.message(lambda msg: msg.text and msg.text.startswith('/bot_stats'))
async def bot_stats_command(message: Message):
    """Показывает статистику бота (только для админов)"""
    user_id = message.from_user.id
    
    # Проверяем права админа
    if user_id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для просмотра статистики.")
        return
    
    db = None
    try:
        db = get_db()
        cur = db.cursor()
        
        # Общая статистика
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM users WHERE balance > 0")
        users_with_balance = cur.fetchone()[0]
        
        cur.execute("SELECT SUM(balance) FROM users")
        total_balance = cur.fetchone()[0] or 0
        
        cur.execute("SELECT COUNT(*) FROM matches")
        total_matches = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM saved_balances")
        saved_balances_count = cur.fetchone()[0]
        
        # Статистика по купонам
        active_coupons = coupon_system.get_active_coupons()
        active_coupons_count = len(active_coupons)
        
        response = f"""📊 Статистика бота WeTogether

👥 Пользователи:
• Всего зарегистрировано: {total_users}
• С положительным балансом: {users_with_balance}
• Общий баланс: ${total_balance:.2f}

💕 Матчи:
• Всего создано: {total_matches}

🎫 Купоны:
• Активных купонов: {active_coupons_count}

💰 Сохраненные балансы:
• Ожидают восстановления: {saved_balances_count}

💾 Система сохранения: ✅ Активна"""
        
        await message.answer(response)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении статистики: {str(e)}")
    finally:
        if db:
            try:
                db.close()
            except:
                pass

# === Пополнить через CryptoBot ===
@dp.callback_query(F.data == "topup_crypto")
async def topup_crypto(callback_query):
    user_id = callback_query.from_user.id
    
    text = """₿ Пополнение через CryptoBot

💡 Введите сумму для пополнения в долларах (например: 5, 10, 25.50)

Минимальная сумма: $1
Максимальная сумма: $100"""
    
    # Устанавливаем состояние для ввода суммы
    try:
        state = FSMContext(storage=dp.storage, key=StorageKey(chat_id=callback_query.message.chat.id, user_id=user_id, bot_id=bot.id))
        await state.set_state(CryptoInput.waiting_for_amount)  # Временно используем это состояние
        await state.update_data(waiting_for_amount=True)
    except Exception as e:
        print(f"Ошибка установки состояния: {e}")
        await callback_query.message.edit_text("❌ Ошибка. Попробуйте позже.")
        return
    
    await callback_query.message.edit_text(text)
    await callback_query.answer()

# === Обработка ввода суммы для CryptoBot ===
@dp.message(CryptoInput.waiting_for_amount)
async def handle_crypto_amount_input(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        
        if amount < 1 or amount > 100:
            await message.answer("❌ Сумма должна быть от $1 до $100. Попробуйте снова:")
            return
        
        user_id = message.from_user.id
        
        # Создаем реальный счет в CryptoBot
        description = f"Пополнение баланса на ${amount:.2f}"
        invoice = await crypto_bot.create_invoice(amount, user_id, description)
        
        if not invoice:
            await message.answer("❌ Ошибка создания счета в CryptoBot. Попробуйте позже.")
            await state.clear()
            return
        
        invoice_id = invoice.get("invoice_id")
        pay_url = invoice.get("pay_url")
        
        # Сохраняем информацию о платеже в базе данных
        db = None
        try:
            db = get_db()
            cur = db.cursor()
            cur.execute("""
                INSERT INTO payments (payment_id, user_id, amount, method, status, invoice_id)
                VALUES (?, ?, ?, 'crypto', 'pending', ?)
            """, (f"crypto_{invoice_id}", user_id, amount, str(invoice_id)))
            db.commit()
            
        except Exception as e:
            print(f"Error saving payment: {e}")
            if db:
                try:
                    db.rollback()
                except:
                    pass
        finally:
            if db:
                try:
                    db.close()
                except:
                    pass
        
        text = f"""₿ Оплата через CryptoBot

💰 Сумма: ${amount:.2f}
🆔 ID счета: {invoice_id}

После оплаты баланс будет зачислен автоматически в течение пары минут.
Нажмите кнопку ниже для оплаты:"""
        
        pay_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Оплатить ${amount:.2f}", url=pay_url)],
            [InlineKeyboardButton(text="🔄 Проверить статус", callback_data=f"check_topup_payment_{invoice_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])
        
        await message.answer(text, reply_markup=pay_kb)

        # Запускаем автоматическую проверку платежа и автозачисление баланса
        try:
            await start_auto_check_payment(message.chat.id, user_id, str(invoice_id), amount)
        except Exception as e:
            print(f"❌ DEBUG: Не удалось запустить авто-проверку платежа: {e}")
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите число (например: 5, 10, 25.50):")
    except Exception as e:
        print(f"❌ CRYPTO ERROR: {e}")
        await message.answer("❌ Ошибка создания платежа. Попробуйте позже.")
        await state.clear()

# === Использовать купон для баланса ===
@dp.callback_query(F.data == "use_balance_coupon")
async def use_balance_coupon(callback_query):
    user_id = callback_query.from_user.id
    
    text = """🎫 Использование купона

Введите код купона в следующем формате:
/coupon КОД_КУПОНА

Например: /coupon WETOGETHER1234

💡 Купоны можно получить:
• При регистрации по реферальной ссылке
• За активность в боте
• От администрации"""
    
    await callback_query.message.edit_text(text)
    await callback_query.answer()

# === Купить супер-лайк ===
@dp.callback_query(F.data == "buy_super_like")
async def buy_super_like(callback_query):
    user_id = callback_query.from_user.id
    balance = get_user_balance(user_id)
    super_like_price = 1.0
    
    if balance < super_like_price:
        await callback_query.message.edit_text("Недостаточно средств на балансе!")
        return
    
    if update_balance(user_id, -super_like_price):
        await callback_query.message.edit_text("⭐ Супер-лайк куплен!\n\nТеперь ваша анкета будет показываться в топе.")
    else:
        await callback_query.message.edit_text("Ошибка при покупке!")
    
    await callback_query.answer()

# === Купить буст профиля ===
@dp.callback_query(F.data == "buy_boost")
async def buy_boost(callback_query):
    user_id = callback_query.from_user.id
    balance = get_user_balance(user_id)
    boost_price = 3.0
    
    if balance < boost_price:
        await callback_query.message.edit_text("Недостаточно средств на балансе!")
        return
    
    if update_balance(user_id, -boost_price):
        await callback_query.message.edit_text("🚀 Буст профиля куплен!\n\nТеперь ваша анкета будет показываться чаще.")
    else:
        await callback_query.message.edit_text("Ошибка при покупке!")
    
    await callback_query.answer()

# === Отменить удаление ===
@dp.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback_query):
    await callback_query.message.edit_text("❌ Удаление отменено.\n\nВаша анкета сохранена.")
    await callback_query.answer()

# === Подтвердить удаление ===
@dp.callback_query(F.data == "confirm_delete")
async def confirm_delete(callback_query):
    user_id = callback_query.from_user.id
    db = None
    try:
        db = get_db()
        cur = db.cursor()
        
        # Сохраняем баланс перед удалением
        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance_result = cur.fetchone()
        saved_balance = balance_result[0] if balance_result else 0.0
        
        # Создаем запись о сохраненном балансе
        cur.execute("""
            INSERT OR REPLACE INTO saved_balances (user_id, balance, saved_at, reason)
            VALUES (?, ?, datetime('now'), 'profile_deletion')
        """, (user_id, saved_balance))
        
        # Удаляем все связанные данные (кроме сохраненного баланса)
        cur.execute("DELETE FROM likes WHERE user_id = ? OR liked_id = ?", (user_id, user_id))
        cur.execute("DELETE FROM matches WHERE user1_id = ? OR user2_id = ?", (user_id, user_id))
        cur.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        
        db.commit()
        
        await callback_query.message.edit_text(
            f"🗑️ Анкета удалена.\n\n"
            f"💰 Ваш баланс ${saved_balance:.2f} сохранен!\n"
            f"💡 При новой регистрации баланс будет восстановлен автоматически."
        )
    except Exception as e:
        await callback_query.message.edit_text(f"❌ Ошибка при удалении: {e}")
    finally:
        if db:
            try:
                db.close()
            except:
                pass
    
    await callback_query.answer()

# === Романтический тур ===
@dp.callback_query(F.data == "romantic_tour")
async def romantic_tour(callback_query):
    user_id = callback_query.from_user.id
    balance = get_user_balance(user_id)
    
    text = f"""💕 Романтический тур - $2

После оплаты вы получите доступ к специальным романтическим заданиям с голосовыми сообщениями.

Ваш баланс: ${balance:.2f}"""
    
    await callback_query.message.edit_text(text, reply_markup=payment_kb)
    await callback_query.answer()

# === Показать баланс ===
@dp.callback_query(F.data == "show_balance")
async def show_balance_callback(callback_query):
    user_id = callback_query.from_user.id
    balance = get_user_balance(user_id)
    
    text = f"""💰 Ваш баланс: {format_balance(balance)}

💳 Пополнить баланс можно через:
• CryptoBot
• Реферальные бонусы
• Купоны"""
    
    balance_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="₿ Пополнить CryptoBot", callback_data="topup_crypto")],
        [InlineKeyboardButton(text="🎫 Использовать купон", callback_data="use_balance_coupon")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=balance_kb)
    await callback_query.answer()

# === Игнорировать матч ===
@dp.callback_query(F.data == "ignore_match")
async def ignore_match(callback_query):
    user_id = callback_query.from_user.id
    db = None
    try:
        db = get_db()
        cur = db.cursor()
        
        # Удаляем матч
        cur.execute("DELETE FROM matches WHERE (user1_id = ? OR user2_id = ?) AND active = TRUE", (user_id, user_id))
        db.commit()
        
        await callback_query.message.edit_text("❌ Матч проигнорирован.")
        await callback_query.answer()
        
    except Exception as e:
        print(f"Error ignoring match: {e}")
        await callback_query.answer("Ошибка при игнорировании матча.")
    finally:
        if db:
            try:
                db.close()
            except:
                pass

# === Начать задания ===
@dp.callback_query(F.data == "start_tasks")
async def start_tasks(callback_query):
    user_id = callback_query.from_user.id
    db = None
    try:
        db = get_db()
        cur = db.cursor()
        
        # Находим матч пользователя
        cur.execute("SELECT id, user1_id, user2_id FROM matches WHERE (user1_id = ? OR user2_id = ?) AND active = TRUE", (user_id, user_id))
        match = cur.fetchone()
        if not match:
            await callback_query.answer("Матч не найден.")
            return
        
        match_id, user1_id, user2_id = match
        
        # Автоматически начинаем первое задание
        await start_first_task(match_id, user1_id, user2_id)
        
        await callback_query.message.edit_text("🎮 Задания начались!\n\nОтвечайте на вопросы вместе с партнером.")
        await callback_query.answer()
        
    except Exception as e:
        print(f"Error starting tasks: {e}")
        await callback_query.answer("Ошибка при запуске заданий.")
    finally:
        if db:
            try:
                db.close()
            except:
                pass

# === Автоматическая проверка платежей ===
async def start_auto_check_payment(chat_id: int, user_id: int, invoice_id: str, amount: float):
    """Запускает автоматическую проверку платежа каждые 10 секунд"""
    
    async def check_payment_loop():
        for i in range(60):  # Проверяем 60 раз (10 минут)
            await asyncio.sleep(10)  # Ждем 10 секунд
            
            # Проверяем статус платежа
            status = await crypto_bot.check_invoice_status(invoice_id)
            
            if status == "paid":
                # Платеж оплачен - пополняем баланс автоматически
                db = None
                try:
                    db = get_db()
                    cur = db.cursor()
                    
                    # Проверяем, не пополнен ли уже баланс
                    cur.execute("SELECT status FROM payments WHERE invoice_id = ?", (invoice_id,))
                    payment_status = cur.fetchone()
                    
                    if payment_status and payment_status[0] == "pending":
                        # Обновляем статус платежа
                        cur.execute("UPDATE payments SET status = 'completed' WHERE invoice_id = ?", (invoice_id,))
                        
                        # Пополняем баланс напрямую в базе
                        try:
                            # Сначала получаем текущий баланс
                            cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
                            current_balance = cur.fetchone()
                            
                            if current_balance:
                                new_balance = current_balance[0] + amount
                                cur.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
                                
                                # Создаем транзакцию
                                cur.execute("""
                                    INSERT INTO transactions (user_id, amount, type, description, status)
                                    VALUES (?, ?, 'topup', 'CryptoBot payment (auto)', 'completed')
                                """, (user_id, amount))
                                
                                db.commit()
                                
                                print(f"✅ DEBUG: Баланс пользователя {user_id} пополнен на ${amount:.2f}. Новый баланс: ${new_balance:.2f}")
                                
                                # Отправляем уведомление о автоматическом пополнении
                                text = f"""✅ Платеж автоматически обработан!

💰 Пополнено: ${amount:.2f}
🆔 ID счета: {invoice_id}
💳 Новый баланс: ${new_balance:.2f}

Ваш баланс обновлен автоматически!"""
                                
                                try:
                                    await bot.send_message(chat_id, text)
                                except:
                                    pass
                                
                                return  # Завершаем цикл
                            else:
                                print(f"❌ DEBUG: Пользователь {user_id} не найден в базе")
                        except Exception as e:
                            print(f"❌ DEBUG: Ошибка при обновлении баланса: {e}")
                            if db:
                                try:
                                    db.rollback()
                                except:
                                    pass
                except Exception as e:
                    print(f"Error in auto check: {e}")
                finally:
                    if db:
                        try:
                            db.close()
                        except:
                            pass
            
            elif status == "expired":
                # Счет истек
                try:
                    await bot.send_message(chat_id, "❌ Счет истек. Создайте новый платеж.")
                except:
                    pass
                return  # Завершаем цикл
    
    # Запускаем автоматическую проверку в фоне
    asyncio.create_task(check_payment_loop())

# === Ручная проверка статуса пополнения CryptoBot ===
@dp.callback_query(F.data.startswith("check_topup_payment_"))
async def check_topup_payment_callback(callback_query):
    user_id = callback_query.from_user.id
    invoice_id = callback_query.data.replace("check_topup_payment_", "")
    try:
        status = await crypto_bot.check_invoice_status(invoice_id)
        if status == "paid":
            # Кредитуем баланс, если еще не зачислен
            db = None
            try:
                db = get_db()
                cur = db.cursor()
                cur.execute("SELECT amount, status FROM payments WHERE invoice_id = ?", (invoice_id,))
                row = cur.fetchone()
                if not row:
                    await callback_query.answer("Платеж не найден.", show_alert=True)
                    return
                amount, current_status = row
                if current_status == "completed":
                    await callback_query.answer("Этот платеж уже зачислен.", show_alert=True)
                    return
                # Обновляем статус и баланс
                cur.execute("UPDATE payments SET status = 'completed' WHERE invoice_id = ?", (invoice_id,))
                cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
                cur.execute(
                    """
                    INSERT INTO transactions (user_id, amount, type, description, status)
                    VALUES (?, ?, 'topup', 'CryptoBot payment (manual check)', 'completed')
                    """,
                    (user_id, amount),
                )
                db.commit()
                await callback_query.answer("✅ Платеж зачислен!", show_alert=True)
                await callback_query.message.edit_text(
                    f"✅ Платеж найден и зачислен.\n\n💰 Сумма: ${amount:.2f}\n🆔 ID счета: {invoice_id}"
                )
            except Exception as e:
                if db:
                    try:
                        db.rollback()
                    except:
                        pass
                print(f"Error on manual topup credit: {e}")
                await callback_query.answer("Ошибка при зачислении платежа.", show_alert=True)
            finally:
                if db:
                    try:
                        db.close()
                    except:
                        pass
        elif status == "pending":
            await callback_query.answer("⏳ Платеж еще не оплачен. Попробуйте позже.", show_alert=True)
        elif status == "expired":
            await callback_query.answer("❌ Счет истек. Создайте новый платеж.", show_alert=True)
        else:
            await callback_query.answer("❌ Не удалось получить статус платежа.", show_alert=True)
    except Exception as e:
        print(f"Error on check_topup_payment: {e}")
        await callback_query.answer("Ошибка при проверке платежа.", show_alert=True)

# === Автоматическое начало романтического тура ===
async def start_romantic_tour(match_id: int, user1_id: int, user2_id: int):
    """Автоматически начинает романтический тур для обоих участников"""
    try:
        # Получаем первое романтическое задание
        task_text = ROMANTIC_TASKS[0]
        
        # Отправляем задание ОБОИМ участникам
        text = f"💕 Романтический тур начался!\n\nРомантическое задание 1:\n{task_text}"
        
        try:
            await bot.send_message(user1_id, text)
        except:
            pass
        try:
            await bot.send_message(user2_id, text)
        except:
            pass
        
        # Устанавливаем состояние для ожидания ответа ОБОИХ участников
        try:
            user1_state_context = FSMContext(storage=dp.storage, key=StorageKey(chat_id=user1_id, user_id=user1_id, bot_id=bot.id))
            user2_state_context = FSMContext(storage=dp.storage, key=StorageKey(chat_id=user2_id, user_id=user2_id, bot_id=bot.id))
        except Exception as e:
            print(f"Ошибка создания состояния: {e}")
            return
        
        await user1_state_context.set_state(TaskAnswer.waiting_for_answer)
        await user1_state_context.update_data(match_id=match_id, task_index=0, is_romantic=True, partner_id=user2_id)
        
        await user2_state_context.set_state(TaskAnswer.waiting_for_answer)
        await user2_state_context.update_data(match_id=match_id, task_index=0, is_romantic=True, partner_id=user1_id)
        
        print(f"✅ DEBUG: Романтический тур автоматически начат для матча {match_id} у ОБОИХ пользователей")
        
    except Exception as e:
        print(f"❌ DEBUG: Ошибка при автоматическом начале романтического тура: {e}")

# === Покупка романтического тура ===
@dp.callback_query(F.data == "buy_romantic_tour")
async def buy_romantic_tour(callback_query):
    user_id = callback_query.from_user.id
    balance = get_user_balance(user_id)
    
    text = f"""💕 Романтический тур - $2

После оплаты вы получите доступ к специальным романтическим заданиям с голосовыми сообщениями.

Ваш баланс: ${balance:.2f}"""
    
    await callback_query.message.edit_text(text, reply_markup=payment_kb)
    await callback_query.answer()

# === Оплата с баланса ===
@dp.callback_query(F.data == "pay_balance")
async def pay_with_balance(callback_query):
    user_id = callback_query.from_user.id
    balance = get_user_balance(user_id)
    tour_price = 2.0
    
    if balance < tour_price:
        await callback_query.answer("Недостаточно средств на балансе!", show_alert=True)
        return
    
    # Списываем средства
    if update_balance(user_id, -tour_price):
        # Создаем транзакцию
        create_payment_transaction(user_id, tour_price, "balance", "completed")
        
        # Обновляем матч и автоматически запускаем романтический тур
        db = None
        try:
            db = get_db()
            cur = db.cursor()
            
            # Обновляем статус оплаты для ЛЮБОГО матча пользователя (активного или неактивного)
            cur.execute("UPDATE matches SET romantic_tour_paid = TRUE WHERE (user1_id = ? OR user2_id = ?)", (user_id, user_id))
            db.commit()
            
            # Находим матч для автоматического запуска тура - ЛЮБОЙ матч пользователя
            cur.execute("SELECT id, user1_id, user2_id FROM matches WHERE (user1_id = ? OR user2_id = ?) AND romantic_tour_paid = TRUE ORDER BY id DESC LIMIT 1", (user_id, user_id))
            match = cur.fetchone()
            
            if match:
                match_id, user1_id, user2_id = match
                
                # Проверяем, завершены ли обычные задания
                cur.execute("SELECT tasks_completed FROM matches WHERE id = ?", (match_id,))
                tasks_completed = cur.fetchone()[0]
                
                if tasks_completed >= REGULAR_TASKS_COUNT:
                    # Обычные задания завершены - запускаем романтический тур НЕМЕДЛЕННО
                    await start_romantic_tour(match_id, user1_id, user2_id)
                    
                    # Отправляем уведомления ОБОИМ пользователям
                    try:
                        await bot.send_message(user1_id, "✅ Романтический тур оплачен!\n\n💕 Романтический тур начался автоматически!")
                    except:
                        pass
                    try:
                        await bot.send_message(user2_id, "✅ Романтический тур оплачен!\n\n💕 Романтический тур начался автоматически!")
                    except:
                        pass
                    
                    await callback_query.message.edit_text("✅ Романтический тур оплачен с баланса!\n\n💕 Романтический тур начался автоматически у ОБОИХ пользователей!")
                else:
                    # Обычные задания еще не завершены
                    await callback_query.message.edit_text("✅ Романтический тур оплачен с баланса!\n\nТур запустится автоматически после завершения 5 обычных заданий.")
            else:
                await callback_query.message.edit_text("✅ Романтический тур оплачен с баланса!\n\nТур запустится после завершения обычных заданий.")
                
        except Exception as e:
            print(f"Error updating match: {e}")
            await callback_query.answer("Ошибка при обновлении матча!", show_alert=True)
        finally:
            if db:
                try:
                    db.close()
                except:
                    pass
    else:
        await callback_query.answer("Ошибка при списании средств!", show_alert=True)
    
    await callback_query.answer()

# === Оплата через CryptoBot ===
@dp.callback_query(F.data == "pay_crypto")
async def pay_with_crypto(callback_query):
    user_id = callback_query.from_user.id
    
    # Создаем счет в CryptoBot
    description = "Романтический тур - доступ к голосовым заданиям"
    invoice = await crypto_bot.create_invoice(2.0, user_id, description)
    
    if not invoice:
        await callback_query.message.edit_text("❌ Ошибка создания счета в CryptoBot. Попробуйте позже.")
        await callback_query.answer()
        return
    
    invoice_id = invoice.get("invoice_id")
    pay_url = invoice.get("pay_url")
    
    # Сохраняем информацию о платеже
    db = None
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("""
            INSERT INTO payments (payment_id, user_id, amount, method, status, invoice_id)
            VALUES (?, ?, ?, 'crypto_romantic', 'pending', ?)
        """, (f"romantic_{invoice_id}", user_id, 2.0, str(invoice_id)))
        db.commit()
    except Exception as e:
        print(f"Error saving payment: {e}")
        await callback_query.message.edit_text("❌ Ошибка сохранения платежа. Попробуйте позже.")
        await callback_query.answer()
        return
    finally:
        if db:
            try:
                db.close()
            except:
                pass
    
    text = f"""💕 Романтический тур - $2

💰 Сумма: $2.00
🆔 ID счета: {invoice_id}

После оплаты вы получите доступ к специальным романтическим заданиям с голосовыми сообщениями.

Нажмите кнопку ниже для оплаты:"""
    
    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить $2.00", url=pay_url)],
        [InlineKeyboardButton(text="🔄 Проверить статус", callback_data=f"check_romantic_payment_{invoice_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=pay_kb)
    await callback_query.answer()

# === Проверка платежа романтического тура ===
@dp.callback_query(F.data.startswith("check_romantic_payment_"))
async def check_romantic_payment_status(callback_query):
    user_id = callback_query.from_user.id
    invoice_id = callback_query.data.replace("check_romantic_payment_", "")
    
    # Проверяем статус платежа через CryptoBot API
    status = await crypto_bot.check_invoice_status(invoice_id)
    
    if status == "paid":
        # Платеж оплачен - активируем романтический тур
        db = None
        try:
            db = get_db()
            cur = db.cursor()
            
            # Обновляем статус платежа
            cur.execute("UPDATE payments SET status = 'completed' WHERE invoice_id = ?", (invoice_id,))
            
            # Активируем романтический тур для пользователя - для ЛЮБОГО матча (активного или неактивного)
            cur.execute("UPDATE matches SET romantic_tour_paid = TRUE WHERE (user1_id = ? OR user2_id = ?)", (user_id, user_id))
            db.commit()
            
            # Находим матч для автоматического запуска тура - ЛЮБОЙ матч пользователя
            cur.execute("SELECT id, user1_id, user2_id FROM matches WHERE (user1_id = ? OR user2_id = ?) AND romantic_tour_paid = TRUE ORDER BY id DESC LIMIT 1", (user_id, user_id))
            match = cur.fetchone()
            
            if match:
                match_id, user1_id, user2_id = match
                
                # Проверяем, завершены ли обычные задания
                cur.execute("SELECT tasks_completed FROM matches WHERE id = ?", (match_id,))
                tasks_completed = cur.fetchone()[0]
                
                if tasks_completed >= REGULAR_TASKS_COUNT:
                    # Обычные задания завершены - запускаем романтический тур НЕМЕДЛЕННО
                    await start_romantic_tour(match_id, user1_id, user2_id)
                    
                    # Отправляем уведомления ОБОИМ пользователям
                    try:
                        await bot.send_message(user1_id, f"✅ Романтический тур оплачен!\n\n💕 Романтический тур начался автоматически!\n🆔 ID счета: {invoice_id}")
                    except:
                        pass
                    try:
                        await bot.send_message(user2_id, f"✅ Романтический тур оплачен!\n\n💕 Романтический тур начался автоматически!\n🆔 ID счета: {invoice_id}")
                    except:
                        pass
                    
                    text = f"""✅ Романтический тур оплачен!

💕 Романтический тур начался автоматически у ОБОИХ пользователей!
🆔 ID счета: {invoice_id}

Начинаем первое романтическое задание!"""
                else:
                    # Обычные задания еще не завершены
                    text = f"""✅ Романтический тур оплачен!

💕 Романтический тур активирован
🆔 ID счета: {invoice_id}

Тур запустится автоматически после завершения 5 обычных заданий!"""
            else:
                text = f"""✅ Романтический тур оплачен!

💕 Романтический тур активирован
🆔 ID счета: {invoice_id}

Тур запустится после завершения обычных заданий!"""
            
            await callback_query.message.edit_text(text)
            await callback_query.answer("Романтический тур активирован!", show_alert=True)
        except Exception as e:
            print(f"Error activating romantic tour: {e}")
            await callback_query.answer("Ошибка активации романтического тура!", show_alert=True)
        finally:
            if db:
                try:
                    db.close()
                except:
                    pass
    
    elif status == "pending":
        await callback_query.answer("⏳ Платеж в процессе обработки. Попробуйте проверить через минуту.", show_alert=True)
    
    elif status == "expired":
        await callback_query.answer("❌ Счет истек. Создайте новый платеж.", show_alert=True)
    
    else:
        await callback_query.answer("❌ Не удалось проверить статус платежа. Попробуйте позже.", show_alert=True)

# === Назад в главное меню ===
@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback_query):
    await callback_query.message.edit_text("🏠 Главное меню")
    await callback_query.answer()

# === Обработка обычных сообщений ===
@dp.message(lambda msg: True)
async def handle_private_messages(message: Message):
    # Обычные сообщения НЕ пересылаются
    # Бот пересылает ТОЛЬКО ответы на задания через process_task_answer
    return

# === Запуск бота ===
async def main():
    retry_count = 0
    max_retries = 10
    
    print("🚀 Запуск бота WeTogether...")
    print("💾 Система сохранения данных активирована")
    
    while retry_count < max_retries:
        try:
            print(f"🤖 Бот запускается... (попытка {retry_count + 1}/{max_retries})")
            
            # Сохраняем текущее состояние перед запуском
            await save_bot_state()
            
        await dp.start_polling(bot)
            break  # Если бот успешно запустился, выходим из цикла
            
    except KeyboardInterrupt:
            print("🛑 Бот остановлен пользователем.")
            await save_bot_state()  # Сохраняем состояние при остановке
            break
            
        except Exception as e:
            retry_count += 1
            print(f"❌ Ошибка подключения: {e}")
            
            # Сохраняем состояние при ошибке
            await save_bot_state()
            
            if retry_count >= max_retries:
                print("❌ Превышено максимальное количество попыток. Бот остановлен.")
                break
                
            wait_time = min(30, retry_count * 10)  # Увеличиваем время ожидания
            print(f"🔄 Перезапуск через {wait_time} секунд...")
            await asyncio.sleep(wait_time)
            
    finally:
            try:
        await bot.session.close()
            except:
                pass
    
    print("🏁 Бот завершил работу.")

# === Функция сохранения состояния бота ===
async def save_bot_state():
    """Сохраняет текущее состояние бота для восстановления при перезапуске"""
    try:
        db = None
        try:
            db = get_db()
            cur = db.cursor()
            
            # Создаем резервную копию важных данных
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bot_backup (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backup_type TEXT NOT NULL,
                    data TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Сохраняем статистику пользователей
            cur.execute("SELECT COUNT(*) FROM users")
            users_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM users WHERE balance > 0")
            users_with_balance = cur.fetchone()[0]
            
            cur.execute("SELECT SUM(balance) FROM users")
            total_balance = cur.fetchone()[0] or 0
            
            backup_data = f"users:{users_count},with_balance:{users_with_balance},total_balance:{total_balance}"
            
            cur.execute("""
                INSERT INTO bot_backup (backup_type, data)
                VALUES ('statistics', ?)
            """, (backup_data,))
            
            db.commit()
            print(f"💾 Состояние бота сохранено: {users_count} пользователей, общий баланс: ${total_balance:.2f}")
            
        except Exception as e:
            print(f"❌ Ошибка сохранения состояния: {e}")
            if db:
                try:
                    db.rollback()
                except:
                    pass
        finally:
            if db:
                try:
                    db.close()
                except:
                    pass
                    
    except Exception as e:
        print(f"❌ Критическая ошибка при сохранении: {e}")

if __name__ == "__main__":
    asyncio.run(main())
