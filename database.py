import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()

    # Таблица домашних заданий
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS homework
                   (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       subject_name TEXT NOT NULL,
                       date TEXT NOT NULL,
                       homework_description TEXT,
                       added_by TEXT,
                       chat_id INTEGER,
                       topic_id INTEGER,
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                   )
                   ''')

    # Таблица файлов домашних заданий
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS homework_files
                   (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       homework_id INTEGER,
                       file_name TEXT NOT NULL,
                       file_type TEXT NOT NULL,
                       original_name TEXT,
                       added_by TEXT,
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                       FOREIGN KEY (homework_id) REFERENCES homework (id) ON DELETE CASCADE
                   )
                   ''')

    # Таблица решений домашних заданий
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS homework_solutions
                   (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       homework_id INTEGER NOT NULL,
                       file_name TEXT NOT NULL,
                       file_type TEXT NOT NULL,
                       original_name TEXT,
                       added_by TEXT,
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                       FOREIGN KEY (homework_id) REFERENCES homework (id) ON DELETE CASCADE
                   )
                   ''')

    # Таблица дней рождения
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS birthdays
                   (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       name TEXT NOT NULL,
                       month INTEGER NOT NULL CHECK (month >= 1 AND month <= 12),
                       day INTEGER NOT NULL CHECK (day >= 1 AND day <= 31),
                       added_by TEXT,
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                   )
                   ''')

    # Таблица зачетов
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS exams
                   (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       subject_name TEXT NOT NULL,
                       exam_date TEXT NOT NULL,
                       description TEXT,
                       notification_sent_3_days BOOLEAN DEFAULT 0,
                       notification_sent_1_day BOOLEAN DEFAULT 0,
                       added_by TEXT,
                       chat_id INTEGER,
                       topic_id INTEGER,
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                   )
                   ''')

    # Таблица файлов зачетов
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS exam_files
                   (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       exam_id INTEGER,
                       file_name TEXT NOT NULL,
                       file_type TEXT NOT NULL,
                       original_name TEXT,
                       added_by TEXT,
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                       FOREIGN KEY (exam_id) REFERENCES exams (id) ON DELETE CASCADE
                   )
                   ''')

    # Таблица папок справочных материалов
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS reference_folders
                   (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       folder_name TEXT NOT NULL,
                       description TEXT,
                       subject_name TEXT,
                       created_by TEXT,
                       chat_id INTEGER,
                       topic_id INTEGER,
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                   )
                   ''')

    # Таблица файлов справочных материалов
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS reference_files
                   (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       folder_id INTEGER NOT NULL,
                       file_name TEXT NOT NULL,
                       file_type TEXT NOT NULL,
                       original_name TEXT,
                       added_by TEXT,
                       file_order INTEGER DEFAULT 0,
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                       FOREIGN KEY (folder_id) REFERENCES reference_folders (id) ON DELETE CASCADE
                   )
                   ''')

    # Таблица запросов на добавление файлов
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS reference_requests
                   (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       folder_id INTEGER NOT NULL,
                       user_id INTEGER NOT NULL,
                       user_name TEXT NOT NULL,
                       description TEXT,
                       status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
                       admin_id INTEGER,
                       admin_name TEXT,
                       decision_date TIMESTAMP,
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                       FOREIGN KEY (folder_id) REFERENCES reference_folders (id) ON DELETE CASCADE
                   )
                   ''')

    # Таблица файлов запросов
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS request_files
                   (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       request_id INTEGER NOT NULL,
                       file_name TEXT NOT NULL,
                       file_type TEXT NOT NULL,
                       original_name TEXT,
                       temp_file_name TEXT NOT NULL,
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                       FOREIGN KEY (request_id) REFERENCES reference_requests (id) ON DELETE CASCADE
                   )
                   ''')

    # Обновляем структуру существующих таблиц
    for table in ['homework', 'homework_files']:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [column[1] for column in cursor.fetchall()]
        if 'added_by' not in columns:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN added_by TEXT")

    cursor.execute("PRAGMA table_info(homework)")
    columns = [column[1] for column in cursor.fetchall()]
    for col in ['chat_id', 'topic_id']:
        if col not in columns:
            cursor.execute(f"ALTER TABLE homework ADD COLUMN {col} INTEGER")

    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

def save_birthdays_to_db():
    """Сохраняет дни рождения из файла в БД"""
    from main import BIRTHDAYS_FILE
    
    birthdays = []
    if os.path.exists(BIRTHDAYS_FILE):
        try:
            with open(BIRTHDAYS_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split('|')
                        if len(parts) >= 3:
                            name = parts[0].strip()
                            month = int(parts[1].strip())
                            day = int(parts[2].strip())
                            birthdays.append((name, month, day))
        except Exception as e:
            logger.error(f"Ошибка чтения файла дней рождения: {e}")
            return
    
    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM birthdays")
        
        for name, month, day in birthdays:
            cursor.execute('INSERT INTO birthdays (name, month, day, added_by) VALUES (?, ?, ?, ?)',
                           (name, month, day, "Система"))
        
        conn.commit()
        logger.info(f"Сохранено {len(birthdays)} дней рождения в БД")
        
    except Exception as e:
        logger.error(f"Ошибка сохранения дней рождения в БД: {e}")
        conn.rollback()
    finally:
        conn.close()

def load_birthdays():
    """Загружает дни рождения из файла"""
    from main import BIRTHDAYS_FILE
    
    birthdays = []
    if os.path.exists(BIRTHDAYS_FILE):
        try:
            with open(BIRTHDAYS_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split('|')
                        if len(parts) >= 3:
                            name = parts[0].strip()
                            month = int(parts[1].strip())
                            day = int(parts[2].strip())
                            birthdays.append((name, month, day))
            
            logger.info(f"Загружено {len(birthdays)} дней рождения из файла")
            save_birthdays_to_db()
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке дней рождения: {e}")
    return birthdays

def add_birthday_to_file(name, month, day, added_by):
    """Добавляет день рождения в файл"""
    from main import BIRTHDAYS_FILE
    
    try:
        with open(BIRTHDAYS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{name}|{month}|{day}|{added_by}\n")
        logger.info(f"День рождения добавлен: {name} - {day}.{month}")
        return True
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return False


def get_birthdays_by_month(month):
    """Возвращает дни рождения для указанного месяца"""
    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, day FROM birthdays WHERE month = ? ORDER BY day', (month,))
    birthdays = cursor.fetchall()
    conn.close()
    return birthdays


def get_month_name(month_num, case='nominative'):
    """Возвращает название месяца в указанном падеже"""
    months_nominative = [
        'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
        'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
    ]
    months_genitive = [
        'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
        'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
    ]

    if 1 <= month_num <= 12:
        if case == 'genitive':
            return months_genitive[month_num - 1]
        else:
            return months_nominative[month_num - 1]
    return ''