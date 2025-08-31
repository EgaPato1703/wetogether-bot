# database.py
import sqlite3

def init_db():
    import os
    # Получаем абсолютный путь к директории скрипта
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, 'users.db')
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Таблица пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            gender TEXT,
            age INTEGER,
            city TEXT,
            bio TEXT,
            photo TEXT,
            balance REAL DEFAULT 0.0,
            referral_code TEXT UNIQUE,
            referred_by INTEGER,
            is_deleted BOOLEAN DEFAULT FALSE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Таблица лайков
    cur.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            liked_id INTEGER,
            is_super_like BOOLEAN DEFAULT FALSE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (liked_id) REFERENCES users (user_id)
        )
    """)

    # Миграция: переименование столбца liker_id -> user_id (если старая схема)
    try:
        cur.execute("PRAGMA table_info(likes)")
        cols = [row[1] for row in cur.fetchall()]
        if "liker_id" in cols and "user_id" not in cols:
            # Пересоздаем таблицу с нужной схемой и переносим данные
            cur.execute("""
                CREATE TABLE IF NOT EXISTS likes_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    liked_id INTEGER,
                    is_super_like BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (liked_id) REFERENCES users (user_id)
                )
            """)
            # Переносим данные, если дополнительных полей нет - подставятся значения по умолчанию
            try:
                cur.execute("INSERT INTO likes_new (id, user_id, liked_id, is_super_like, created_at) SELECT id, liker_id, liked_id, COALESCE(is_super_like, 0), COALESCE(created_at, CURRENT_TIMESTAMP) FROM likes")
            except Exception:
                cur.execute("INSERT INTO likes_new (id, user_id, liked_id) SELECT id, liker_id, liked_id FROM likes")
            cur.execute("DROP TABLE likes")
            cur.execute("ALTER TABLE likes_new RENAME TO likes")
            conn.commit()
    except Exception as e:
        print(f"Likes table migration skipped/failed: {e}")

    # Таблица матчей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user1_id INTEGER,
            user2_id INTEGER,
            active BOOLEAN DEFAULT TRUE,
            chat_active BOOLEAN DEFAULT FALSE,
            tasks_completed INTEGER DEFAULT 0,
            romantic_tasks_completed INTEGER DEFAULT 0,
            romantic_tour_paid BOOLEAN DEFAULT FALSE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user1_id) REFERENCES users (user_id),
            FOREIGN KEY (user2_id) REFERENCES users (user_id)
        )
    """)

    # Таблица активных чатов (для управления пересылкой сообщений)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS active_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            user1_id INTEGER,
            user2_id INTEGER,
            chat_type TEXT DEFAULT 'tasks', -- 'tasks' или 'free_chat'
            is_active BOOLEAN DEFAULT TRUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (match_id) REFERENCES matches (id),
            FOREIGN KEY (user1_id) REFERENCES users (user_id),
            FOREIGN KEY (user2_id) REFERENCES users (user_id)
        )
    """)

    # Таблица для сохранения балансов при удалении анкет
    cur.execute("""
        CREATE TABLE IF NOT EXISTS saved_balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            balance REAL NOT NULL,
            saved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            reason TEXT DEFAULT 'profile_deletion',
            restored BOOLEAN DEFAULT FALSE
        )
    """)

    # Таблица заданий матчей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS match_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            task_index INTEGER,
            user_id INTEGER,
            answer TEXT,
            answer_type TEXT DEFAULT 'text',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (match_id) REFERENCES matches (id),
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """)

    # Таблица сообщений
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            sender_id INTEGER,
            content TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (match_id) REFERENCES matches (id),
            FOREIGN KEY (sender_id) REFERENCES users (user_id)
        )
    """)

    # Таблица купонов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            discount_percent INTEGER,
            max_uses INTEGER,
            current_uses INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Таблица купонов для пополнения баланса
    cur.execute("""
        CREATE TABLE IF NOT EXISTS balance_coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            amount REAL,
            max_uses INTEGER,
            current_uses INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Таблица транзакций
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            type TEXT,
            description TEXT,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """)

    # Таблица платежей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id TEXT UNIQUE,
            user_id INTEGER,
            amount REAL,
            method TEXT,
            invoice_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """)

    # === НОВЫЕ ТАБЛИЦЫ ДЛЯ ПРЕМИУМ ФУНКЦИЙ ===

    # Таблица супер-лайков
    cur.execute("""
        CREATE TABLE IF NOT EXISTS super_likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            target_id INTEGER,
            is_active BOOLEAN DEFAULT TRUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (target_id) REFERENCES users (user_id)
        )
    """)

    # Таблица бустов профилей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS profile_boosts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            boost_type TEXT, -- 'boost', 'unlimited_likes'
            expires_at DATETIME,
            is_active BOOLEAN DEFAULT TRUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """)

    # Таблица просмотров лайков
    cur.execute("""
        CREATE TABLE IF NOT EXISTS like_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            viewer_id INTEGER,
            viewed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (viewer_id) REFERENCES users (user_id)
        )
    """)

    conn.commit()
    conn.close()

def get_db():
    import os
    # Получаем абсолютный путь к директории скрипта
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, 'users.db')
    return sqlite3.connect(db_path)

# === Функции для управления активными чатами ===

def create_active_chat(match_id, user1_id, user2_id, chat_type='tasks'):
    """Создает активный чат для матча"""
    db = get_db()
    cur = db.cursor()
    
    # Сначала деактивируем все предыдущие чаты для этого матча
    cur.execute("UPDATE active_chats SET is_active = FALSE WHERE match_id = ?", (match_id,))
    
    # Создаем новый активный чат
    cur.execute("""
        INSERT INTO active_chats (match_id, user1_id, user2_id, chat_type, is_active)
        VALUES (?, ?, ?, ?, TRUE)
    """, (match_id, user1_id, user2_id, chat_type))
    
    # Обновляем статус матча
    cur.execute("UPDATE matches SET chat_active = TRUE WHERE id = ?", (match_id,))
    
    db.commit()
    db.close()

def deactivate_chat(match_id):
    """Деактивирует чат для матча"""
    db = get_db()
    cur = db.cursor()
    
    cur.execute("UPDATE active_chats SET is_active = FALSE WHERE match_id = ?", (match_id,))
    cur.execute("UPDATE matches SET chat_active = FALSE WHERE id = ?", (match_id,))
    
    db.commit()
    db.close()

def is_chat_active(match_id):
    """Проверяет, активен ли чат для матча"""
    db = get_db()
    cur = db.cursor()
    
    cur.execute("SELECT is_active FROM active_chats WHERE match_id = ? AND is_active = TRUE", (match_id,))
    result = cur.fetchone()
    
    db.close()
    return result is not None

def get_active_chat_info(user_id):
    """Получает информацию об активном чате пользователя"""
    db = get_db()
    cur = db.cursor()
    
    cur.execute("""
        SELECT ac.match_id, ac.user1_id, ac.user2_id, ac.chat_type, ac.is_active,
               m.tasks_completed, m.romantic_tasks_completed, m.romantic_tour_paid
        FROM active_chats ac
        JOIN matches m ON ac.match_id = m.id
        WHERE ac.is_active = TRUE 
        AND (ac.user1_id = ? OR ac.user2_id = ?)
    """, (user_id, user_id))
    
    result = cur.fetchone()
    db.close()
    
    if result:
        return {
            'match_id': result[0],
            'user1_id': result[1],
            'user2_id': result[2],
            'chat_type': result[3],
            'is_active': result[4],
            'tasks_completed': result[5],
            'romantic_tasks_completed': result[6],
            'romantic_tour_paid': result[7]
        }
    return None

def can_send_messages(user_id, match_id):
    """Проверяет, может ли пользователь отправлять сообщения в данном матче"""
    from config import REGULAR_TASKS_COUNT, ROMANTIC_TASKS_COUNT
    
    chat_info = get_active_chat_info(user_id)
    
    if not chat_info or chat_info['match_id'] != match_id:
        return False
    
    # Если это чат с заданиями, проверяем что задания еще идут
    if chat_info['chat_type'] == 'tasks':
        # Проверяем, есть ли активные романтические задания
        if chat_info['romantic_tour_paid'] and chat_info['romantic_tasks_completed'] < ROMANTIC_TASKS_COUNT:
            # Есть активные романтические задания - можно отправлять сообщения
            return True
        elif chat_info['tasks_completed'] < REGULAR_TASKS_COUNT:
            # Есть активные обычные задания - можно отправлять сообщения
            return True
        else:
            # Все задания завершены - нельзя отправлять сообщения
            return False
    
    # Для свободного чата всегда можно отправлять сообщения
    return True