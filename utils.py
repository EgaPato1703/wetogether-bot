# utils.py
import re
from typing import Optional
from database import get_db

def validate_age(age_str: str) -> Optional[int]:
    """Проверяет и возвращает валидный возраст"""
    try:
        age = int(age_str)
        if 14 <= age <= 100:
            return age
    except ValueError:
        pass
    return None

def validate_age_range(age_range: str) -> Optional[tuple[int, int]]:
    """Проверяет и возвращает валидный возрастной диапазон"""
    pattern = r'^(\d+)-(\d+)$'
    match = re.match(pattern, age_range.strip())
    if match:
        min_age, max_age = int(match.group(1)), int(match.group(2))
        if 14 <= min_age <= max_age <= 100:
            return min_age, max_age
    return None

def format_balance(amount: float) -> str:
    """Форматирует баланс для отображения"""
    return f"${amount:.2f}"

def get_user_stats(user_id: int) -> dict:
    """Получает статистику пользователя"""
    db = None
    try:
        db = get_db()
        cur = db.cursor()
        
        # Количество лайков (получено)
        cur.execute("SELECT COUNT(*) FROM likes WHERE liked_id = ?", (user_id,))
        likes_received = cur.fetchone()[0]
        
        # Количество поставленных лайков
        cur.execute("SELECT COUNT(*) FROM likes WHERE user_id = ?", (user_id,))
        likes_given = cur.fetchone()[0]
        
        # Количество матчей
        cur.execute("SELECT COUNT(*) FROM matches WHERE user1_id = ? OR user2_id = ?", (user_id, user_id))
        matches_count = cur.fetchone()[0]
        
        # Количество рефералов
        cur.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
        referrals_count = cur.fetchone()[0]
        
        return {
            'likes_received': likes_received,
            'likes_given': likes_given,
            'matches_count': matches_count,
            'referrals_count': referrals_count
        }
    except Exception as e:
        print(f"Error getting stats: {e}")
        return {
            'likes_received': 0,
            'likes_given': 0,
            'matches_count': 0,
            'referrals_count': 0
        }
    finally:
        if db:
            try:
                db.close()
            except:
                pass

def is_valid_coupon_code(code: str) -> bool:
    """Проверяет валидность кода купона"""
    return bool(re.match(r'^[A-Z0-9]{4,12}$', code.upper()))

def generate_payment_link(amount: float, method: str) -> str:
    """Генерирует ссылку для оплаты"""
    if method == "stars":
        return f"https://stars.com/pay?amount={amount}"
    elif method == "crypto":
        return f"https://cryptobot.com/pay?amount={amount}"
    return ""

def sanitize_text(text: str) -> str:
    """Очищает текст от потенциально опасных символов"""
    # Удаляем HTML теги
    text = re.sub(r'<[^>]+>', '', text)
    # Ограничиваем длину
    if len(text) > 1000:
        text = text[:1000] + "..."
    return text.strip()

def get_user_balance(user_id: int) -> float:
    """Получает баланс пользователя"""
    db = None
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cur.fetchone()
        return float(result[0]) if result else 0.0
    except Exception as e:
        print(f"Error getting balance: {e}")
        return 0.0
    finally:
        if db:
            try:
                db.close()
            except:
                pass

def update_balance(user_id: int, amount: float) -> bool:
    """Обновляет баланс пользователя"""
    db = None
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        db.commit()
        return True
    except Exception as e:
        print(f"Error updating balance: {e}")
        if db:
            try:
                db.rollback()
            except:
                pass
        return False
    finally:
        if db:
            try:
                db.close()
            except:
                pass

def get_user_referral_code(user_id: int) -> str:
    """Получает реферальный код пользователя"""
    db = None
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT referral_code FROM users WHERE user_id = ?", (user_id,))
        result = cur.fetchone()
        return result[0] if result else ""
    except Exception as e:
        print(f"Error getting referral code: {e}")
        return "ERROR"
    finally:
        if db:
            try:
                db.close()
            except:
                pass

def get_user_referral_stats(user_id: int) -> dict:
    """Получает статистику рефералов пользователя"""
    db = None
    try:
        db = get_db()
        cur = db.cursor()
        
        # Количество рефералов
        cur.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
        referrals_count = cur.fetchone()[0]
        
        # Общий заработок с рефералов (фиксированный бонус за каждого реферала)
        total_earned = referrals_count * 1.0  # $1 за каждого реферала
        
        return {
            'referrals_count': referrals_count,
            'total_earned': total_earned
        }
    except Exception as e:
        print(f"Error getting referral stats: {e}")
        return {
            'referrals_count': 0,
            'total_earned': 0.0
        }
    finally:
        if db:
            try:
                db.close()
            except:
                pass

def apply_coupon(user_id: int, coupon_code: str) -> tuple[bool, str]:
    """Применяет купон к пользователю"""
    db = None
    try:
        db = get_db()
        cur = db.cursor()
        
        # Проверяем существование купона для пополнения баланса
        cur.execute("SELECT amount, current_uses, max_uses FROM balance_coupons WHERE code = ? AND is_active = TRUE", (coupon_code,))
        result = cur.fetchone()
        
        if not result:
            return False, "Купон не найден"
        
        amount, current_uses, max_uses = result
        
        if current_uses >= max_uses:
            return False, "Купон уже использован максимальное количество раз"
        
        # Применяем купон
        try:
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            cur.execute("UPDATE balance_coupons SET current_uses = current_uses + 1 WHERE code = ?", (coupon_code,))
            db.commit()
            return True, f"Купон применен! Добавлено ${amount:.2f}"
        except Exception as e:
            db.rollback()
            return False, f"Ошибка применения купона: {e}"
    except Exception as e:
        print(f"Error applying coupon: {e}")
        return False, f"Ошибка применения купона: {e}"
    finally:
        if db:
            try:
                db.close()
            except:
                pass

def create_payment_transaction(user_id: int, amount: float, payment_method: str, status: str = 'pending') -> bool:
    """Создает транзакцию оплаты"""
    db = None
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("""
            INSERT INTO transactions (user_id, amount, type, description, status, created_at)
            VALUES (?, ?, 'payment', ?, ?, datetime('now'))
        """, (user_id, amount, payment_method, status))
        db.commit()
        return True
    except Exception as e:
        print(f"Error creating transaction: {e}")
        if db:
            try:
                db.rollback()
            except:
                pass
        return False
    finally:
        if db:
            try:
                db.close()
            except:
                pass

def create_crypto_payment(user_id: int, amount: float) -> str:
    """Создает платеж через CryptoBot"""
    try:
        import time
        
        # Здесь должна быть реальная интеграция с CryptoBot API
        # Пока возвращаем заглушку
        payment_id = f"crypto_{user_id}_{int(time.time())}"
        
        # Создаем транзакцию
        create_payment_transaction(user_id, amount, "crypto", "pending")
        
        return f"https://t.me/CryptoBot?start=pay_{payment_id}_{amount}"
    except Exception as e:
        print(f"Error creating crypto payment: {e}")
        return ""

def process_crypto_payment(payment_id: str) -> bool:
    """Обрабатывает подтверждение платежа через CryptoBot"""
    try:
        # Здесь должна быть проверка статуса платежа через CryptoBot API
        # Пока просто возвращаем True
        return True
    except Exception as e:
        print(f"Error processing crypto payment: {e}")
        return False
