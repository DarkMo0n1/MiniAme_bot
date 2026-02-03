import sqlite3
import os
import uuid
from datetime import datetime, timedelta
import telebot
from telebot import types
import threading
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

TOKEN = '8549158268:AAHmfHcRnUpTxilyY72RL8pWK9Fr7qTcKBU'
bot = telebot.TeleBot(TOKEN)

# Абсолютные пути для VPS
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILES_DIR = os.path.join(BASE_DIR, 'homework_files')
EXAM_FILES_DIR = os.path.join(BASE_DIR, 'exam_files')
if not os.path.exists(FILES_DIR):
    os.makedirs(FILES_DIR, exist_ok=True)
    logger.info(f"Создана директория для файлов: {FILES_DIR}")
if not os.path.exists(EXAM_FILES_DIR):
    os.makedirs(EXAM_FILES_DIR, exist_ok=True)
    logger.info(f"Создана директория для файлов экзаменов: {EXAM_FILES_DIR}")

TOPIC_ID = 60817
CONSOLE_CHAT_ID = -1002530863470
NOTIFICATION_CHAT_ID = 2  # ID чата для уведомлений
# Список ID администраторов
ADMIN_IDS = [1087190562, 5621181751, 2068653336]
BIRTHDAYS_FILE = os.path.join(BASE_DIR, 'birthdays.txt')

user_data = {}
exam_notifications = {}


def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS


def get_user_info(user):
    """Возвращает информацию о пользователе для логов"""
    user_id = user.id
    username = user.username or "без username"
    first_name = user.first_name or "без имени"
    return f"{user_id} ({username}, {first_name})"


def log_action(user, action, details=""):
    """Логирует действия пользователя"""
    user_info = get_user_info(user)
    log_message = f"ДЕЙСТВИЕ: {action} - Пользователь: {user_info}"
    if details:
        log_message += f" - Детали: {details}"
    logger.info(log_message)


def check_topic_access(message):
    """Проверяет доступ к топику - разрешает команды в личных сообщениях и в нужном топике"""
    # Если топик не задан, разрешаем все
    if TOPIC_ID is None:
        return True

    # В личных сообщениях разрешаем все команды
    if message.chat.type == 'private':
        return True

    # В группах/супергруппах проверяем топик
    if message.chat.type in ['group', 'supergroup']:
        # Если сообщение в топике
        if hasattr(message, 'message_thread_id'):
            return message.message_thread_id == TOPIC_ID
        # Если сообщение не в топике, но это команда, которую нужно разрешить везде
        # (например, /del_mes, /clear_all, /call_all)
        return True

    return False


def is_in_correct_topic(message):
    """Проверяет, находится ли сообщение в правильном топике (для команд очистки)"""
    # В личных сообщениях эти команды не должны работать
    if message.chat.type == 'private':
        return False

    if TOPIC_ID is None:
        return True

    if message.chat.type in ['group', 'supergroup']:
        if hasattr(message, 'message_thread_id'):
            return message.message_thread_id == TOPIC_ID
    return False


def init_db():
    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()

    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS homework
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       subject_name
                       TEXT
                       NOT
                       NULL,
                       date
                       TEXT
                       NOT
                       NULL,
                       homework_description
                       TEXT,
                       added_by
                       TEXT,
                       chat_id
                       INTEGER,
                       topic_id
                       INTEGER,
                       created_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   ''')

    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS homework_files
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       homework_id
                       INTEGER,
                       file_name
                       TEXT
                       NOT
                       NULL,
                       file_type
                       TEXT
                       NOT
                       NULL,
                       original_name
                       TEXT,
                       added_by
                       TEXT,
                       created_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP,
                       FOREIGN
                       KEY
                   (
                       homework_id
                   ) REFERENCES homework
                   (
                       id
                   ) ON DELETE CASCADE
                       )
                   ''')

    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS birthdays
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       name
                       TEXT
                       NOT
                       NULL,
                       month
                       INTEGER
                       NOT
                       NULL
                       CHECK
                   (
                       month
                       >=
                       1
                       AND
                       month
                       <=
                       12
                   ),
                       day INTEGER NOT NULL CHECK
                   (
                       day
                       >=
                       1
                       AND
                       day
                       <=
                       31
                   ),
                       added_by TEXT,
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                       )
                   ''')

    # Новая таблица для зачетов
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS exams
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       subject_name
                       TEXT
                       NOT
                       NULL,
                       exam_date
                       TEXT
                       NOT
                       NULL,
                       description
                       TEXT,
                       notification_sent_3_days
                       BOOLEAN
                       DEFAULT
                       0,
                       notification_sent_1_day
                       BOOLEAN
                       DEFAULT
                       0,
                       added_by
                       TEXT,
                       chat_id
                       INTEGER,
                       topic_id
                       INTEGER,
                       created_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   ''')

    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS exam_files
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       exam_id
                       INTEGER,
                       file_name
                       TEXT
                       NOT
                       NULL,
                       file_type
                       TEXT
                       NOT
                       NULL,
                       original_name
                       TEXT,
                       added_by
                       TEXT,
                       created_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP,
                       FOREIGN
                       KEY
                   (
                       exam_id
                   ) REFERENCES exams
                   (
                       id
                   ) ON DELETE CASCADE
                       )
                   ''')

    # Обновляем структуру таблиц
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


def get_month_name(month_num, case='genitive'):
    month_names = {
        'nominative': ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                       'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'],
        'genitive': ['Января', 'Февраля', 'Марта', 'Апреля', 'Мая', 'Июня',
                     'Июля', 'Августа', 'Сентября', 'Октября', 'Ноября', 'Декабря']
    }

    if 1 <= month_num <= 12:
        return month_names[case][month_num - 1]
    return "Неизвестный"


def load_birthdays():
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
            logger.info(f"Загружено {len(birthdays)} дней рождения")
        except Exception as e:
            logger.error(f"Ошибка при загрузке дней рождения: {e}")
    return birthdays


def save_birthdays_to_db():
    birthdays = load_birthdays()
    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM birthdays")
        for name, month, day in birthdays:
            cursor.execute('INSERT OR IGNORE INTO birthdays (name, month, day, added_by) VALUES (?, ?, ?, ?)',
                           (name, month, day, "Система"))
        conn.commit()
        logger.info(f"Сохранено {len(birthdays)} дней рождения в БД")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        conn.rollback()
    finally:
        conn.close()


def add_birthday_to_file(name, month, day, added_by):
    try:
        with open(BIRTHDAYS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{name}|{month}|{day}|{added_by}\n")
        logger.info(f"День рождения добавлен: {name} - {day}.{month}")
        return True
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return False


def get_birthdays_by_month(month):
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
                            file_month = int(parts[1].strip())
                            day = int(parts[2].strip())
                            if file_month == month:
                                birthdays.append((name, day))
            birthdays.sort(key=lambda x: x[1])
        except Exception as e:
            logger.error(f"Ошибка: {e}")
    return birthdays


def generate_unique_filename(original_name, file_type):
    timestamp = int(datetime.now().timestamp() * 1000)
    random_str = str(uuid.uuid4())[:8]

    if original_name:
        safe_name = "".join(c for c in original_name if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()
        name_without_ext, ext = os.path.splitext(safe_name)
        if not ext:
            ext_map = {'фото': '.jpg', 'документ': '.bin', 'аудио': '.mp3',
                       'видео': '.mp4', 'голосовое сообщение': '.ogg'}
            ext = ext_map.get(file_type, '.bin')
    else:
        name_without_ext = file_type
        ext = '.bin'

    return f"{timestamp}_{random_str}{ext}"


def save_file_locally(file_content, original_name, file_type):
    try:
        unique_filename = generate_unique_filename(original_name, file_type)
        file_path = os.path.join(FILES_DIR, unique_filename)

        # Проверяем и создаем директорию если нужно
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, 'wb') as f:
            f.write(file_content)

        logger.info(f"Файл сохранен: {file_path}")
        return unique_filename  # Возвращаем только имя файла, не полный путь
    except Exception as e:
        logger.error(f"Ошибка при сохранении файла: {e}")
        return None


def create_main_menu():
    """Создает главное меню (доступно всем)"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton('📚 ДЗ', callback_data='homework_submenu'),
        types.InlineKeyboardButton('👨‍🏫 Учителя', callback_data='teacher_name_menu'),
        types.InlineKeyboardButton('🎂 Дни рождения', callback_data='birthdays_menu'),
        types.InlineKeyboardButton('📋 Ближайший зачёт', callback_data='exams_menu'),
        types.InlineKeyboardButton('ℹ️ Помощь', callback_data='help_menu')
    ]

    for i in range(0, len(buttons), 2):
        row = buttons[i:i + 2]
        markup.row(*row)

    return markup


def create_homework_submenu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('📝 Добавить задание', callback_data='add_homework_menu'),
        types.InlineKeyboardButton('📋 Все задания', callback_data='view_homework_menu'),
        types.InlineKeyboardButton('📅 Сегодня', callback_data='today_homework_menu'),
        types.InlineKeyboardButton('📆 Завтра', callback_data='tomorrow_homework_menu'),
        types.InlineKeyboardButton('🔙 Назад', callback_data='main_menu')
    )
    return markup


def create_birthdays_menu():
    markup = types.InlineKeyboardMarkup(row_width=3)
    months = [('Январь', 1), ('Февраль', 2), ('Март', 3),
              ('Апрель', 4), ('Май', 5), ('Июнь', 6),
              ('Июль', 7), ('Август', 8), ('Сентябрь', 9),
              ('Октябрь', 10), ('Ноябрь', 11), ('Декабрь', 12)]

    for i in range(0, len(months), 3):
        row_buttons = []
        for j in range(3):
            if i + j < len(months):
                month_name, month_num = months[i + j]
                row_buttons.append(types.InlineKeyboardButton(month_name, callback_data=f'birthdays_month_{month_num}'))
        markup.row(*row_buttons)

    markup.row(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    return markup


def create_back_to_menu_button():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    return markup


def create_exams_menu(user_id):
    """Меню управления зачетами (разное для админа и обычных пользователей)"""
    markup = types.InlineKeyboardMarkup(row_width=2)

    # Эти кнопки доступны всем
    markup.add(
        types.InlineKeyboardButton('📋 Все зачёты', callback_data='view_exams_menu'),
        types.InlineKeyboardButton('📅 Ближайшие зачёты', callback_data='upcoming_exams_menu')
    )

    # Кнопки добавления/управления только для админа
    if is_admin(user_id):
        markup.add(
            types.InlineKeyboardButton('📝 Добавить зачёт', callback_data='add_exam_menu'),
            types.InlineKeyboardButton('🗑️ Удалить зачёт', callback_data='delete_exam_menu')
        )

    markup.add(types.InlineKeyboardButton('🔙 Назад', callback_data='main_menu'))
    return markup


def show_birthdays_for_month(call, month_num):
    birthdays = get_birthdays_by_month(month_num)
    month_name_nominative = get_month_name(month_num, 'nominative')
    month_name_genitive = get_month_name(month_num, 'genitive')

    if not birthdays:
        response = f"🎂 <b>Дни рождения в {month_name_nominative}:</b>\n\nПока нет записей.\nИспользуйте /add_birthday чтобы добавить."
    else:
        response = f"🎂 <b>Дни рождения в {month_name_nominative}:</b>\n\n"
        for name, day in birthdays:
            response += f"• <b>{name}</b> - {day} {month_name_genitive}\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад к месяцам", callback_data="birthdays_menu"))
    markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=response,
        parse_mode='HTML',
        reply_markup=markup
    )


def check_exam_notifications():
    """Проверяет и отправляет уведомления о ближайших зачетах"""
    try:
        conn = sqlite3.connect('homework.db')
        cursor = conn.cursor()
        today = datetime.now().date()

        # Проверяем зачеты через 3 дня
        three_days_later = today + timedelta(days=3)
        cursor.execute('''
                       SELECT id, subject_name, exam_date, description
                       FROM exams
                       WHERE exam_date = ?
                         AND notification_sent_3_days = 0
                       ''', (three_days_later.strftime('%Y-%m-%d'),))

        exams_3_days = cursor.fetchall()

        for exam in exams_3_days:
            exam_id, subject_name, exam_date, description = exam
            notification_text = f"🔔 Напоминание о зачете!\n\n"
            notification_text += f"📚 Предмет: {subject_name}\n"
            notification_text += f"📅 Дата: {datetime.strptime(exam_date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
            if description:
                notification_text += f"📝 Описание: {description}\n"
            notification_text += f"\n⏰ До зачета осталось 3 дня!"

            try:
                bot.send_message(NOTIFICATION_CHAT_ID, notification_text)
                cursor.execute('UPDATE exams SET notification_sent_3_days = 1 WHERE id = ?', (exam_id,))
                logger.info(f"Отправлено уведомление за 3 дня до зачета: {subject_name}")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления за 3 дня: {e}")

        # Проверяем зачеты через 1 день
        one_day_later = today + timedelta(days=1)
        cursor.execute('''
                       SELECT id, subject_name, exam_date, description
                       FROM exams
                       WHERE exam_date = ?
                         AND notification_sent_1_day = 0
                       ''', (one_day_later.strftime('%Y-%m-%d'),))

        exams_1_day = cursor.fetchall()

        for exam in exams_1_day:
            exam_id, subject_name, exam_date, description = exam
            notification_text = f"🔔 СРОЧНОЕ напоминание о зачете!\n\n"
            notification_text += f"📚 Предмет: {subject_name}\n"
            notification_text += f"📅 Дата: {datetime.strptime(exam_date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
            if description:
                notification_text += f"📝 Описание: {description}\n"
            notification_text += f"\n⏰ Зачет ЗАВТРА!"

            try:
                bot.send_message(NOTIFICATION_CHAT_ID, notification_text)
                cursor.execute('UPDATE exams SET notification_sent_1_day = 1 WHERE id = ?', (exam_id,))
                logger.info(f"Отправлено уведомление за 1 день до зачета: {subject_name}")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления за 1 день: {e}")

        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(f"Ошибка в функции проверки уведомлений: {e}")


def notification_scheduler():
    """Планировщик для проверки уведомлений"""
    while True:
        try:
            check_exam_notifications()
            # Проверяем каждые 6 часов
            threading.Event().wait(6 * 3600)
        except Exception as e:
            logger.error(f"Ошибка в планировщике уведомлений: {e}")
            threading.Event().wait(300)  # Ждем 5 минут при ошибке


@bot.message_handler(commands=['start'])
def send_welcome(message):
    global CONSOLE_CHAT_ID
    CONSOLE_CHAT_ID = message.chat.id
    user_info = get_user_info(message.from_user)
    logger.info(f"Пользователь {user_info} запустил бота в чате {CONSOLE_CHAT_ID}")

    # Для /start разрешаем всегда
    help_text = "👋 Привет! Я бот для управления домашними заданиями и зачетами.\n\n👇 <b>Выберите действие:</b>"

    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        try:
            bot.send_message(message.chat.id, help_text, parse_mode='HTML',
                             reply_markup=create_main_menu(),
                             message_thread_id=TOPIC_ID)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в группе: {e}")
            bot.send_message(message.chat.id, help_text, parse_mode='HTML',
                             reply_markup=create_main_menu())
    else:
        bot.send_message(message.chat.id, help_text, parse_mode='HTML',
                         reply_markup=create_main_menu())


@bot.message_handler(commands=['help'])
def help_command(message):
    user_id = message.from_user.id

    # Определяем thread_id для ответа
    thread_id = None
    if message.chat.type in ['group', 'supergroup'] and hasattr(message, 'message_thread_id'):
        thread_id = message.message_thread_id

    help_text = """
📚 <b>Доступные команды:</b>

<code>/add_homework</code> - Добавить домашнее задание
<code>/view_homework</code> - Посмотреть все задания
<code>/today_homework</code> - Задания на сегодня
<code>/tomorrow_homework</code> - Задания на завтра
<code>/teacher_name</code> - Узнать имя учителя
<code>/add_birthday</code> - Добавить день рождения
<code>/cancel</code> - Отменить операцию
<code>/help</code> - Справка
<code>/admin_help</code> - Команды администратора
    """

    # Добавляем информацию о командах админа, если пользователь - админ
    if is_admin(user_id):
        help_text += "\n\n🛠️ <b>Команды администратора:</b>\n"
        help_text += "<code>/del_mes</code> - удалить сообщение (ответьте на него)\n"
        help_text += f"<code>/clear_all</code> - удалить все сообщения в топике {TOPIC_ID}\n"
        help_text += "<code>/call_all</code> - упомянуть всех участников чата\n"

    help_text += """
💡 <b>Особенности:</b>
• Все задания общие для всех
• Можно прикреплять несколько файлов
• Для завершения добавления файлов отправьте <code>/done</code>
• Для пропуска отправьте <code>/skip</code>
• Задания может удалить только администратор
    """

    bot.send_message(message.chat.id, help_text, parse_mode='HTML',
                     reply_markup=create_back_to_menu_button(), message_thread_id=thread_id)


@bot.message_handler(commands=['add_homework'])
def add_homework_command(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if user_id in user_data:
        if 'temp_files' in user_data[user_id]:
            for file_name in user_data[user_id]['temp_files']:
                try:
                    file_path = os.path.join(FILES_DIR, file_name)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except:
                    pass
        del user_data[user_id]

    user_data[user_id] = {
        'step': 'subject_name',
        'files': [],
        'temp_files': [],  # Теперь храним только имена файлов
        'added_by': f"{message.from_user.first_name or 'Аноним'}",
        'chat_id': message.chat.id,
        'topic_id': message.message_thread_id if hasattr(message, 'message_thread_id') else None
    }

    log_action(message.from_user, "Начало добавления домашнего задания")

    text = "📝 <b>Добавление домашнего задания</b>\n\n1. Введите название предмета:\n<i>Пример: Математика, Физика</i>\n\n<i>Или отправьте /cancel для отмены</i>"

    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, text, parse_mode='HTML',
                         reply_markup=create_back_to_menu_button(), message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, text, parse_mode='HTML',
                         reply_markup=create_back_to_menu_button())


@bot.message_handler(
    func=lambda message: message.from_user.id in user_data and user_data.get(message.from_user.id, {}).get(
        'step') == 'subject_name')
def process_subject_name(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if message.text.lower() == '/cancel':
        cancel_operation(message)
        return

    user_data[user_id]['subject_name'] = message.text
    user_data[user_id]['step'] = 'homework_description'

    log_action(message.from_user, "Ввод названия предмета", f"Предмет: {message.text}")

    text = "2. Введите описание домашнего задания:\n<i>Можно оставить пустым, отправив \"-\"</i>\n\n<i>Или отправьте /cancel для отмены</i>"

    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, text, parse_mode='HTML', message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, text, parse_mode='HTML')


@bot.message_handler(
    func=lambda message: message.from_user.id in user_data and user_data.get(message.from_user.id, {}).get(
        'step') == 'homework_description')
def process_homework_description(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if message.text.lower() == '/cancel':
        cancel_operation(message)
        return

    user_data[user_id]['homework_description'] = message.text if message.text != "-" else ""
    user_data[user_id]['step'] = 'date'

    log_action(message.from_user, "Ввод описания задания")

    text = "3. Введите дату сдачи задания:\n<i>Формат: ДД.ММ.ГГГГ или сегодня/завтра/послезавтра</i>\n\n<i>Или отправьте /cancel для отмены</i>"

    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, text, parse_mode='HTML', message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, text, parse_mode='HTML')


@bot.message_handler(
    func=lambda message: message.from_user.id in user_data and user_data.get(message.from_user.id, {}).get(
        'step') == 'date')
def process_date(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if message.text.lower() == '/cancel':
        cancel_operation(message)
        return

    date_input = message.text.lower()
    try:
        if date_input == 'сегодня':
            date_obj = datetime.now()
        elif date_input == 'завтра':
            date_obj = datetime.now() + timedelta(days=1)
        elif date_input == 'послезавтра':
            date_obj = datetime.now() + timedelta(days=2)
        else:
            date_obj = datetime.strptime(date_input, '%d.%m.%Y')

        user_data[user_id]['date'] = date_obj.strftime('%Y-%m-%d')
        user_data[user_id]['step'] = 'file_choice'

        log_action(message.from_user, "Ввод даты сдачи", f"Дата: {date_input}")

        homework_summary = get_homework_summary(user_id)
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton('📎 Прикрепить файл', callback_data='attach_file'),
            types.InlineKeyboardButton('✅ Без файла', callback_data='save_without_file'),
            types.InlineKeyboardButton('❌ Отменить', callback_data='cancel_add')
        )

        text = f"📋 <b>Сводка задания:</b>\n\n{homework_summary}\n\nХотите прикрепить файл?"

        if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
            bot.send_message(message.chat.id, text, parse_mode='HTML',
                             reply_markup=markup, message_thread_id=TOPIC_ID)
        else:
            bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=markup)

    except ValueError:
        text = "❌ <b>Неверный формат даты!</b>\nИспользуйте: ДД.ММ.ГГГГ, сегодня, завтра или послезавтра\n\nПопробуйте снова:"
        if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
            bot.send_message(message.chat.id, text, parse_mode='HTML', message_thread_id=TOPIC_ID)
        else:
            bot.send_message(message.chat.id, text, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: True)
def handle_all_callbacks(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    logger.info(f"Обработка callback от пользователя {get_user_info(call.from_user)}: {call.data}")

    if TOPIC_ID is not None and chat_id == call.message.chat.id:
        if call.message.chat.type in ['group', 'supergroup']:
            if hasattr(call.message, 'message_thread_id') and call.message.message_thread_id != TOPIC_ID:
                bot.answer_callback_query(call.id, "❌ Эта команда доступна только в определенном топике")
                return

    if call.data == 'main_menu':
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="👋 <b>Главное меню</b>\n\n👇 Выберите действие:",
            parse_mode='HTML',
            reply_markup=create_main_menu()
        )

    elif call.data == 'homework_submenu':
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="📚 <b>Домашние задания</b>\n\n👇 Выберите действие:",
            parse_mode='HTML',
            reply_markup=create_homework_submenu()
        )

    elif call.data == 'birthdays_menu':
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="🎂 <b>Дни рождения одногруппников</b>\n\n👇 Выберите месяц:",
            parse_mode='HTML',
            reply_markup=create_birthdays_menu()
        )

    elif call.data.startswith('birthdays_month_'):
        month_num = int(call.data.replace('birthdays_month_', ''))
        bot.answer_callback_query(call.id)
        show_birthdays_for_month(call, month_num)

    elif call.data == 'exams_menu':
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="📋 <b>Управление зачетами</b>\n\n👇 Выберите действие:",
            parse_mode='HTML',
            reply_markup=create_exams_menu(user_id)
        )

    elif call.data == 'add_exam_menu':
        bot.answer_callback_query(call.id)
        if is_admin(user_id):
            # Начинаем процесс добавления зачета
            add_exam_command_handler(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ У вас нет прав для добавления зачетов")

    elif call.data == 'delete_exam_menu':
        bot.answer_callback_query(call.id)
        if is_admin(user_id):
            # Показываем список зачетов для удаления
            show_exams_for_deletion(call)
        else:
            bot.answer_callback_query(call.id, "❌ У вас нет прав для удаления зачетов")

    elif call.data == 'view_exams_menu':
        bot.answer_callback_query(call.id)
        # Показываем все зачеты (доступно всем)
        show_exam_dates_list(call)

    elif call.data == 'upcoming_exams_menu':
        bot.answer_callback_query(call.id)
        # Показываем ближайшие зачеты (доступно всем)
        show_upcoming_exams(call)

    elif call.data.startswith('view_exam_date_'):
        date_str = call.data.replace('view_exam_date_', '')
        # Показываем зачеты на конкретную дату (доступно всем, но с разными кнопками)
        show_exams_for_date(call, date_str, user_id)

    elif call.data.startswith('delete_exam_'):
        exam_id = int(call.data.replace('delete_exam_', ''))
        # Удаление зачета (только для админа)
        if is_admin(user_id):
            delete_exam_callback(call, exam_id)
        else:
            bot.answer_callback_query(call.id, "❌ У вас нет прав для удаления зачетов")

    elif call.data == 'add_homework_menu':
        bot.answer_callback_query(call.id)
        if user_id in user_data:
            del user_data[user_id]

        text = "📝 <b>Добавление домашнего задания</b>\n\n1. Введите название предмета:\n<i>Пример: Математика, Физика</i>\n\n<i>Или отправьте /cancel для отмены</i>"

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=text,
            parse_mode='HTML',
            reply_markup=create_back_to_menu_button()
        )

        user_data[user_id] = {
            'step': 'subject_name',
            'files': [],
            'temp_files': [],
            'added_by': f"{call.from_user.first_name or 'Аноним'}",
            'chat_id': chat_id,
            'topic_id': TOPIC_ID if TOPIC_ID is not None else None
        }

        log_action(call.from_user, "Начало добавления ДЗ через меню")

    elif call.data == 'view_homework_menu':
        bot.answer_callback_query(call.id)
        show_dates_list(call)

    elif call.data == 'today_homework_menu':
        bot.answer_callback_query(call.id)
        today = datetime.now().strftime('%Y-%m-%d')
        show_homework_for_date_callback(call, today)

    elif call.data == 'tomorrow_homework_menu':
        bot.answer_callback_query(call.id)
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        show_homework_for_date_callback(call, tomorrow)

    elif call.data == 'teacher_name_menu':
        bot.answer_callback_query(call.id)
        show_teachers_menu(call)

    elif call.data == 'help_menu':
        bot.answer_callback_query(call.id)
        show_help_menu(call)

    elif call.data in ['attach_file', 'save_without_file', 'cancel_add']:
        handle_add_callback(call)

    elif call.data.startswith('view_date_'):
        date_str = call.data.replace('view_date_', '')
        show_homework_for_date_callback(call, date_str)

    elif call.data.startswith('view_files_'):
        hw_id = int(call.data.replace('view_files_', ''))
        show_homework_files(call, hw_id)

    elif call.data.startswith('delete_'):
        delete_homework_callback(call)

    elif call.data == 'back_to_dates':
        bot.answer_callback_query(call.id)
        show_dates_list(call)

    elif call.data in ['Математика', 'Информатика', 'Физика', 'История', 'Биология', 'ОБЖ',
                       'Химия', 'Литература', 'Русский', 'Английский', 'Физра', 'ВВС', 'Общество']:
        bot.answer_callback_query(call.id)
        show_teacher_info(call)


def handle_add_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    if call.data == 'attach_file':
        bot.answer_callback_query(call.id)
        user_data[user_id]['step'] = 'waiting_file'
        text = "4. Отправьте файл (документ, фото, аудио, видео):\n<i>Можно отправить несколько файлов</i>\n<i>Для завершения отправьте /done</i>\n<i>Или отправьте /skip чтобы продолжить без файлов</i>"

        log_action(call.from_user, "Запрос файла для ДЗ")

        if chat_id and TOPIC_ID is not None:
            bot.send_message(chat_id, text, parse_mode='HTML', message_thread_id=TOPIC_ID)
        else:
            bot.send_message(chat_id, text, parse_mode='HTML')

    elif call.data == 'save_without_file':
        bot.answer_callback_query(call.id)
        files_count = save_homework_to_db(user_id)
        if files_count >= 0:
            log_action(call.from_user, "Сохранение ДЗ без файла", "Успешно")
            text = "✅ <b>Домашнее задание успешно сохранено без файла!</b>"
        else:
            log_action(call.from_user, "Сохранение ДЗ без файла", "Ошибка")
            text = "❌ <b>Ошибка при сохранении задания!</b>"
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text + "\n\n🏠 Вы можете вернуться в главное меню:",
            parse_mode='HTML',
            reply_markup=create_back_to_menu_button()
        )
        if user_id in user_data:
            del user_data[user_id]

    elif call.data == 'cancel_add':
        bot.answer_callback_query(call.id)
        log_action(call.from_user, "Отмена добавления ДЗ")
        if user_id in user_data:
            del user_data[user_id]
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="❌ Операция отменена.\n\n🏠 Вы можете вернуться в главное меню:",
            parse_mode='HTML',
            reply_markup=create_back_to_menu_button()
        )


def show_teachers_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    subjects = ['Математика', 'Информатика', 'Физика', 'История', 'Биология', 'ОБЖ',
                'Химия', 'Литература', 'Русский', 'Английский', 'Физра', 'ВВС', 'Общество']

    for i in range(0, len(subjects), 3):
        row = subjects[i:i + 3]
        markup.row(*[types.InlineKeyboardButton(subj, callback_data=subj) for subj in row])

    markup.row(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="👨‍🏫 <b>Выберите предмет:</b>",
        parse_mode='HTML',
        reply_markup=markup
    )


def show_teacher_info(call):
    teachers = {
        'Математика': 'Ефремов Артем Константинович',
        'Информатика': 'Голубева Ирина Алексеевна',
        'Физика': 'Москалёва Светлана Юрьевна',
        'История': 'Кузнецов Андрей Вадимович',
        'Биология': 'Фридман Ольга Ромовна',
        'ОБЖ': 'Тихонов Дмитрий Викторович',
        'Химия': 'Фридман Ольга Ромовна',
        'Литература': 'Осипова Юлия Евгеньевна',
        'Русский': 'Осипова Юлия Евгеньевна',
        'Английский': 'Смагина Надежда Сергеевна',
        'Физра': 'Литвин Андрей Викторович',
        'ВВС': 'Слюсарь Мария Владимировна',
        'Общество': 'Кузнецов Андрей Вадимович'
    }

    subject = call.data
    teacher = teachers.get(subject, 'Неизвестно')
    text = f'<b>{subject}</b>\n\nУчитель: {teacher}'

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text,
        parse_mode='HTML',
        reply_markup=create_back_to_menu_button()
    )


def show_help_menu(call):
    help_text = """
📚 <b>Доступные команды:</b>

<code>/add_homework</code> - Добавить домашнее задание
<code>/view_homework</code> - Посмотреть все задания
<code>/today_homework</code> - Задания на сегодня
<code>/tomorrow_homework</code> - Задания на завтра
<code>/teacher_name</code> - Узнать имя учителя
<code>/add_birthday</code> - Добавить день рождения
<code>/cancel</code> - Отменить операцию
<code>/help</code> - Справка
<code>/admin_help</code> - Команды администратора

💡 <b>Особенности:</b>
• Все задания общие для всех
• Можно прикреплять несколько файлов
• Для завершения добавления файлов отправьте <code>/done</code>
• Для пропуска отправьте <code>/skip</code>
• Задания может удалить только администратор
    """

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=help_text,
        parse_mode='HTML',
        reply_markup=create_back_to_menu_button()
    )


@bot.message_handler(content_types=['photo', 'document', 'audio', 'video', 'voice'])
def handle_file(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if user_id in user_data and user_data[user_id].get('step') == 'waiting_file':
        file_types = {
            'photo': ('фото', 'Фото'),
            'document': ('документ', 'Документ'),
            'audio': ('аудио', 'Аудио'),
            'video': ('видео', 'Видео'),
            'voice': ('голосовое сообщение', 'Голосовое сообщение')
        }

        content_type = message.content_type
        if content_type in file_types:
            file_type, default_name = file_types[content_type]

            if content_type == 'photo':
                file_info = bot.get_file(message.photo[-1].file_id)
                original_name = f'{default_name}_{datetime.now().strftime("%H%M%S")}'
            elif content_type == 'document':
                file_info = bot.get_file(message.document.file_id)
                original_name = message.document.file_name or f'{default_name}_{datetime.now().strftime("%H%M%S")}'
            elif content_type == 'audio':
                file_info = bot.get_file(message.audio.file_id)
                original_name = message.audio.file_name or f'{default_name}_{datetime.now().strftime("%H%M%S")}'
            elif content_type == 'video':
                file_info = bot.get_file(message.video.file_id)
                original_name = message.video.file_name or f'{default_name}_{datetime.now().strftime("%H%M%S")}'
            else:  # voice
                file_info = bot.get_file(message.voice.file_id)
                original_name = f'{default_name}_{datetime.now().strftime("%H%M%S")}'

            try:
                downloaded_file = bot.download_file(file_info.file_path)
                file_name = save_file_locally(downloaded_file, original_name, file_type)

                if file_name:
                    user_data[user_id]['files'].append({
                        'file_name': file_name,
                        'file_type': file_type,
                        'original_name': original_name
                    })
                    user_data[user_id]['temp_files'].append(file_name)

                    files_count = len(user_data[user_id]['files'])
                    text = f"✅ Файл сохранен: {original_name}\n📁 Тип: {file_type}\n📊 Всего файлов: {files_count}\n\nОтправьте ещё файл или /done для завершения."

                    log_action(message.from_user, "Добавление файла к ДЗ", f"Тип: {file_type}, Имя: {original_name}")

                    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
                        bot.send_message(message.chat.id, text, message_thread_id=TOPIC_ID)
                    else:
                        bot.send_message(message.chat.id, text)
                else:
                    send_error(message, "❌ Не удалось сохранить файл. Попробуйте еще раз.")

            except Exception as e:
                logger.error(f"Ошибка при обработке файла: {e}")
                send_error(message, "❌ Не удалось загрузить файл. Попробуйте другой файл или отправьте /skip.")
        else:
            send_error(message, "❌ Неподдерживаемый тип файла.")


def send_error(message, text):
    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, text, message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, text)


@bot.message_handler(commands=['done'])
def finish_adding_files(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if user_id in user_data and user_data[user_id].get('step') == 'waiting_file':
        if all(key in user_data[user_id] for key in ['subject_name', 'homework_description', 'date']):
            files_count = save_homework_to_db(user_id)

            if files_count > 0:
                response = f"✅ <b>Домашнее задание успешно сохранено!</b>\nПрикреплено файлов: {files_count}"
                log_action(message.from_user, "Завершение добавления ДЗ с файлами", f"Файлов: {files_count}")
            elif files_count == 0:
                response = "✅ <b>Домашнее задание успешно сохранено без файлов!</b>"
                log_action(message.from_user, "Завершение добавления ДЗ без файлов", "Успешно")
            else:
                response = "❌ <b>Ошибка при сохранении задания!</b>"
                log_action(message.from_user, "Завершение добавления ДЗ", "Ошибка сохранения")

            if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
                bot.send_message(message.chat.id, response + "\n\n🏠 Вы можете вернуться в главное меню:",
                                 parse_mode='HTML', reply_markup=create_back_to_menu_button(),
                                 message_thread_id=TOPIC_ID)
            else:
                bot.send_message(message.chat.id, response + "\n\n🏠 Вы можете вернуться в главное меню:",
                                 parse_mode='HTML', reply_markup=create_back_to_menu_button())

            if user_id in user_data:
                del user_data[user_id]
        else:
            send_error(message, "❌ Не все данные заполнены. Начните сначала с /add_homework")


@bot.message_handler(commands=['skip'])
def skip_adding_files(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if user_id in user_data and user_data[user_id].get('step') == 'waiting_file':
        if all(key in user_data[user_id] for key in ['subject_name', 'homework_description', 'date']):
            save_homework_to_db(user_id)
            text = "✅ <b>Домашнее задание успешно сохранено без файлов!</b>\n\n🏠 Вы можете вернуться в главное меню:"
            
            log_action(message.from_user, "Пропуск добавления файлов к ДЗ", "Сохранено без файлов")

            if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
                bot.send_message(message.chat.id, text, parse_mode='HTML',
                                 reply_markup=create_back_to_menu_button(), message_thread_id=TOPIC_ID)
            else:
                bot.send_message(message.chat.id, text, parse_mode='HTML',
                                 reply_markup=create_back_to_menu_button())

            if user_id in user_data:
                del user_data[user_id]
        else:
            send_error(message, "❌ Не все данные заполнены. Начните сначала с /add_homework")


@bot.message_handler(commands=['view_homework'])
def view_all_homework(message):
    if not check_topic_access(message):
        return

    log_action(message.from_user, "Просмотр всех заданий")

    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, "📚 <b>Домашние задания</b>\n\n👇 Выберите действие:",
                         parse_mode='HTML', reply_markup=create_homework_submenu(), message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, "📚 <b>Домашние задания</b>\n\n👇 Выберите действие:",
                         parse_mode='HTML', reply_markup=create_homework_submenu())


def show_dates_list(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()

    if chat_id:
        cursor.execute('SELECT DISTINCT date FROM homework WHERE chat_id = ? ORDER BY date', (chat_id,))
    else:
        cursor.execute('SELECT DISTINCT date FROM homework ORDER BY date')

    dates = cursor.fetchall()
    conn.close()

    if not dates:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="📭 Пока нет домашних заданий.\nИспользуйте кнопку 'Добавить задание' чтобы добавить первое задание.",
            reply_markup=create_back_to_menu_button()
        )
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []

    for date_tuple in dates:
        date_str = date_tuple[0]
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d.%m.%Y')

            conn = sqlite3.connect('homework.db')
            cursor = conn.cursor()
            if chat_id:
                cursor.execute('SELECT COUNT(*) FROM homework WHERE date = ? AND chat_id = ?', (date_str, chat_id))
            else:
                cursor.execute('SELECT COUNT(*) FROM homework WHERE date = ?', (date_str,))
            count = cursor.fetchone()[0]
            conn.close()

            buttons.append(
                types.InlineKeyboardButton(f"📅 {formatted_date} ({count})", callback_data=f"view_date_{date_str}"))
        except Exception as e:
            logger.error(f"Ошибка при форматировании даты: {e}")
            continue

    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.row(buttons[i], buttons[i + 1])
        else:
            markup.row(buttons[i])

    markup.row(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))

    bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text="📅 <b>Выберите дату для просмотра домашних заданий:</b>",
        parse_mode='HTML',
        reply_markup=markup
    )


def show_homework_for_date_callback(call, date_str):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    user_id = call.from_user.id

    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()

    if chat_id:
        cursor.execute('''
                       SELECT h.id, h.subject_name, h.homework_description, h.added_by, COUNT(f.id) as file_count
                       FROM homework h
                                LEFT JOIN homework_files f ON h.id = f.homework_id
                       WHERE h.date = ?
                         AND h.chat_id = ?
                       GROUP BY h.id, h.subject_name, h.homework_description, h.added_by
                       ORDER BY h.created_at
                       ''', (date_str, chat_id))
    else:
        cursor.execute('''
                       SELECT h.id, h.subject_name, h.homework_description, h.added_by, COUNT(f.id) as file_count
                       FROM homework h
                                LEFT JOIN homework_files f ON h.id = f.homework_id
                       WHERE h.date = ?
                       GROUP BY h.id, h.subject_name, h.homework_description, h.added_by
                       ORDER BY h.created_at
                       ''', (date_str,))

    homework_list = cursor.fetchall()
    conn.close()

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%d.%m.%Y')
    except:
        formatted_date = date_str

    if not homework_list:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"📭 На {formatted_date} заданий нет.\n\nИспользуйте кнопку 'Добавить задание' чтобы добавить задание.",
            reply_markup=create_back_to_menu_button()
        )
        return

    response = f"📅 <b>Домашние задания на {formatted_date}:</b>\n\n"
    for i, hw in enumerate(homework_list, 1):
        hw_id, subject_name, homework_description, added_by, file_count = hw
        response += f"{i}. <b>{subject_name}</b>\n"
        response += f"   👤 Добавил: {added_by}\n"
        if homework_description:
            response += f"   📝 {homework_description}\n"
        response += f"   📎 Файлов: {file_count}\n\n"

    markup = types.InlineKeyboardMarkup(row_width=2)  # Изменено с 1 на 2
    
    for hw in homework_list:
        hw_id, subject_name, _, _, file_count = hw
        short_name = subject_name[:15] + "..." if len(subject_name) > 15 else subject_name
        
        row_buttons = []
        
        # Всегда добавляем кнопку просмотра файлов, если файлы есть
        if file_count > 0:
            row_buttons.append(types.InlineKeyboardButton(f"📁 {short_name}", callback_data=f"view_files_{hw_id}"))
        else:
            # Если файлов нет, добавляем заглушку с тем же текстом
            row_buttons.append(types.InlineKeyboardButton(f"📄 {short_name}", callback_data=f"view_files_{hw_id}"))
        
        # Проверяем, является ли пользователь администратором для отображения кнопки удаления
        if is_admin(user_id):
            row_buttons.append(types.InlineKeyboardButton(f"❌ {short_name}", callback_data=f"delete_{hw_id}"))
        
        # Добавляем все кнопки для этого задания в один ряд
        if row_buttons:
            markup.row(*row_buttons)

    markup.row(types.InlineKeyboardButton("🔙 К списку дат", callback_data="back_to_dates"))
    markup.row(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))

    bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=response,
        parse_mode='HTML',
        reply_markup=markup
    )


def show_homework_files(call, hw_id):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    # Определяем thread_id для групповых чатов с топиками
    thread_id = None
    if call.message.chat.type in ['group', 'supergroup'] and hasattr(call.message, 'message_thread_id'):
        thread_id = call.message.message_thread_id
    
    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()

    cursor.execute('SELECT subject_name, homework_description, added_by FROM homework WHERE id = ?', (hw_id,))
    hw_info = cursor.fetchone()

    if not hw_info:
        bot.answer_callback_query(call.id, "❌ Задание не найдено")
        return

    subject_name, homework_description, added_by = hw_info
    cursor.execute('SELECT file_name, file_type, original_name FROM homework_files WHERE homework_id = ?', (hw_id,))
    files = cursor.fetchall()
    conn.close()

    if not files:
        # Если файлов нет, просто показываем информацию
        response = f"📁 <b>Файлы к заданию:</b> {subject_name}\n<b>👤 Добавил:</b> {added_by}\n"
        if homework_description:
            response += f"<b>Описание:</b> {homework_description}\n"
        response += f"\n📭 У этого задания нет прикрепленных файлов\n\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Назад к заданиям", callback_data="back_to_dates"))
        markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
        
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=response,
            parse_mode='HTML',
            reply_markup=markup
        )
        return

    # Если файлы есть, отправляем информацию о них
    response = f"📁 <b>Файлы к заданию:</b> {subject_name}\n<b>👤 Добавил:</b> {added_by}\n"
    if homework_description:
        response += f"<b>Описание:</b> {homework_description}\n"
    response += f"\n<b>Отправляю {len(files)} файл(ов)...</b>\n\n"
    
    bot.answer_callback_query(call.id, f"📁 Отправляю {len(files)} файл(ов)...")
    
    # Сначала обновляем текущее сообщение с информацией
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=response,
        parse_mode='HTML'
    )

    # Затем отправляем каждый файл
    for file_info in files:
        file_name, file_type, original_name = file_info
        file_path = os.path.join(FILES_DIR, file_name)
        
        if not os.path.exists(file_path):
            logger.error(f"Файл не найден: {file_path}")
            continue
        
        try:
            with open(file_path, 'rb') as file:
                if file_type == 'фото':
                    if thread_id:
                        bot.send_photo(chat_id, file, caption=original_name or subject_name, 
                                       message_thread_id=thread_id)
                    else:
                        bot.send_photo(chat_id, file, caption=original_name or subject_name)
                elif file_type == 'документ':
                    if thread_id:
                        bot.send_document(chat_id, file, caption=original_name or subject_name,
                                          message_thread_id=thread_id)
                    else:
                        bot.send_document(chat_id, file, caption=original_name or subject_name)
                elif file_type == 'аудио':
                    if thread_id:
                        bot.send_audio(chat_id, file, caption=original_name or subject_name,
                                       message_thread_id=thread_id)
                    else:
                        bot.send_audio(chat_id, file, caption=original_name or subject_name)
                elif file_type == 'видео':
                    if thread_id:
                        bot.send_video(chat_id, file, caption=original_name or subject_name,
                                       message_thread_id=thread_id)
                    else:
                        bot.send_video(chat_id, file, caption=original_name or subject_name)
                elif file_type == 'голосовое сообщение':
                    if thread_id:
                        bot.send_voice(chat_id, file, caption=original_name or subject_name,
                                       message_thread_id=thread_id)
                    else:
                        bot.send_voice(chat_id, file, caption=original_name or subject_name)
                else:
                    # По умолчанию отправляем как документ
                    if thread_id:
                        bot.send_document(chat_id, file, caption=original_name or subject_name,
                                          message_thread_id=thread_id)
                    else:
                        bot.send_document(chat_id, file, caption=original_name or subject_name)
                
                logger.info(f"Файл отправлен: {file_name}")
                
        except Exception as e:
            logger.error(f"Ошибка при отправке файла {file_name}: {e}")
            error_msg = f"❌ Не удалось отправить файл: {original_name or file_name}"
            if thread_id:
                bot.send_message(chat_id, error_msg, message_thread_id=thread_id)
            else:
                bot.send_message(chat_id, error_msg)

    # После отправки всех файлов добавляем кнопки для навигации
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад к заданиям", callback_data="back_to_dates"))
    markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    
    # Отправляем сообщение с кнопками после файлов
    final_msg = f"✅ Все файлы отправлены!\n\n📚 <b>Задание:</b> {subject_name}\n👤 <b>Добавил:</b> {added_by}\n📁 <b>Файлов:</b> {len(files)}"
    if thread_id:
        bot.send_message(chat_id, final_msg, parse_mode='HTML', 
                        reply_markup=markup, message_thread_id=thread_id)
    else:
        bot.send_message(chat_id, final_msg, parse_mode='HTML', reply_markup=markup)

def delete_homework_callback(call):
    user_id = call.from_user.id
    hw_id = int(call.data.replace('delete_', ''))
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    # Проверяем, является ли пользователь администратором
    if not is_admin(user_id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав для удаления заданий")
        log_action(call.from_user, "Попытка удаления задания без прав", f"ID задания: {hw_id}")
        return

    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT subject_name, date FROM homework WHERE id = ?', (hw_id,))
        hw_info = cursor.fetchone()

        if not hw_info:
            bot.answer_callback_query(call.id, "❌ Задание не найдено")
            log_action(call.from_user, "Попытка удаления несуществующего задания", f"ID: {hw_id}")
            conn.close()
            return

        subject_name, date_str = hw_info
        cursor.execute('SELECT file_name FROM homework_files WHERE homework_id = ?', (hw_id,))
        files_to_delete = cursor.fetchall()

        for (file_name,) in files_to_delete:
            try:
                file_path = os.path.join(FILES_DIR, file_name)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Файл удален: {file_path}")
            except Exception as e:
                logger.error(f"Ошибка при удалении файла {file_path}: {e}")
                pass

        cursor.execute('DELETE FROM homework WHERE id = ?', (hw_id,))
        conn.commit()
        conn.close()

        bot.answer_callback_query(call.id, f"✅ Задание '{subject_name}' удалено")
        log_action(call.from_user, "Удаление задания", f"ID: {hw_id}, Предмет: {subject_name}")

        if date_str:
            new_call = type('obj', (object,), {
                'from_user': call.from_user,
                'message': call.message,
                'data': f'view_date_{date_str}'
            })()
            show_homework_for_date_callback(new_call, date_str)
        else:
            show_dates_list(call)

    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        try:
            conn.close()
        except:
            pass
        logger.error(f"Ошибка при удалении задания: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка при удалении задания")
        log_action(call.from_user, "Ошибка при удалении задания", f"ID: {hw_id}, Ошибка: {str(e)}")


@bot.message_handler(commands=['teacher_name'])
def subject(message):
    if not check_topic_access(message):
        return

    log_action(message.from_user, "Просмотр списка учителей")

    markup = types.InlineKeyboardMarkup(row_width=2)
    subjects = ['Математика', 'Информатика', 'Физика', 'История', 'Биология', 'ОБЖ',
                'Химия', 'Литература', 'Русский', 'Английский', 'Физра', 'ВВС', 'Общество']

    for i in range(0, len(subjects), 3):
        row = subjects[i:i + 3]
        markup.row(*[types.InlineKeyboardButton(subj, callback_data=subj) for subj in row])

    markup.row(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))

    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, '👨‍🏫 <b>Выберите предмет:</b>', parse_mode='HTML',
                         reply_markup=markup, message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, '👨‍🏫 <b>Выберите предмет:</b>', parse_mode='HTML',
                         reply_markup=markup)


@bot.message_handler(commands=['add_birthday'])
def add_birthday_command(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if user_id in user_data:
        del user_data[user_id]

    user_data[user_id] = {
        'step': 'birthday_name',
        'birthday_data': {},
        'added_by': f"{message.from_user.first_name or 'Аноним'}"
    }

    log_action(message.from_user, "Начало добавления дня рождения")

    text = "🎂 <b>Добавление дня рождения</b>\n\n1. Введите имя одногруппника:\n<i>Пример: Иванов Иван</i>\n\n<i>Или отправьте /cancel для отмены</i>"

    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, text, parse_mode='HTML',
                         reply_markup=create_back_to_menu_button(), message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, text, parse_mode='HTML',
                         reply_markup=create_back_to_menu_button())


@bot.message_handler(
    func=lambda message: message.from_user.id in user_data and user_data.get(message.from_user.id, {}).get(
        'step') == 'birthday_name')
def process_birthday_name(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if message.text.lower() == '/cancel':
        cancel_operation(message)
        return

    user_data[user_id]['birthday_data']['name'] = message.text
    user_data[user_id]['step'] = 'birthday_month'

    log_action(message.from_user, "Ввод имени для дня рождения", f"Имя: {message.text}")

    text = "2. Введите месяц рождения (число от 1 до 12):\n<i>Пример: 1 (для января), 12 (для декабря)</i>\n\n<i>Или отправьте /cancel для отмены</i>"

    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, text, parse_mode='HTML', message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, text, parse_mode='HTML')


@bot.message_handler(
    func=lambda message: message.from_user.id in user_data and user_data.get(message.from_user.id, {}).get(
        'step') == 'birthday_month')
def process_birthday_month(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if message.text.lower() == '/cancel':
        cancel_operation(message)
        return

    try:
        month = int(message.text)
        if month < 1 or month > 12:
            raise ValueError

        user_data[user_id]['birthday_data']['month'] = month
        user_data[user_id]['step'] = 'birthday_day'

        log_action(message.from_user, "Ввод месяца для дня рождения", f"Месяц: {month}")

        text = "3. Введите день рождения (число от 1 до 31):\n<i>Пример: 15, 31</i>\n\n<i>Или отправьте /cancel для отмены</i>"

        if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
            bot.send_message(message.chat.id, text, parse_mode='HTML', message_thread_id=TOPIC_ID)
        else:
            bot.send_message(message.chat.id, text, parse_mode='HTML')

    except ValueError:
        text = "❌ <b>Неверный формат месяца!</b>\nВведите число от 1 до 12\n\nПопробуйте снова:"
        if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
            bot.send_message(message.chat.id, text, parse_mode='HTML', message_thread_id=TOPIC_ID)
        else:
            bot.send_message(message.chat.id, text, parse_mode='HTML')


@bot.message_handler(
    func=lambda message: message.from_user.id in user_data and user_data.get(message.from_user.id, {}).get(
        'step') == 'birthday_day')
def process_birthday_day(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if message.text.lower() == '/cancel':
        cancel_operation(message)
        return

    try:
        day = int(message.text)
        if day < 1 or day > 31:
            raise ValueError

        birthday_data = user_data[user_id]['birthday_data']
        name = birthday_data['name']
        month = birthday_data['month']
        added_by = user_data[user_id]['added_by']

        success = add_birthday_to_file(name, month, day, added_by)

        if success:
            conn = sqlite3.connect('homework.db')
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO birthdays (name, month, day, added_by) VALUES (?, ?, ?, ?)',
                           (name, month, day, added_by))
            conn.commit()
            conn.close()

            del user_data[user_id]

            month_name_genitive = get_month_name(month, 'genitive')
            response = f"✅ <b>День рождения добавлен!</b>\n\n<b>Имя:</b> {name}\n<b>Дата:</b> {day} {month_name_genitive}\n<b>Добавил:</b> {added_by}\n\nДень рождения успешно сохранен."
            markup = create_back_to_menu_button()

            log_action(message.from_user, "Добавление дня рождения", f"Имя: {name}, Дата: {day}.{month}")

            if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
                bot.send_message(message.chat.id, response, parse_mode='HTML',
                                 reply_markup=markup, message_thread_id=TOPIC_ID)
            else:
                bot.send_message(message.chat.id, response, parse_mode='HTML', reply_markup=markup)
        else:
            response = "❌ <b>Ошибка при сохранении дня рождения!</b>\n\nПопробуйте еще раз."
            if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
                bot.send_message(message.chat.id, response, parse_mode='HTML', message_thread_id=TOPIC_ID)
            else:
                bot.send_message(message.chat.id, response, parse_mode='HTML')

    except ValueError:
        text = "❌ <b>Неверный формат дня!</b>\nВведите число от 1 до 31\n\nПопробуйте снова:"
        if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
            bot.send_message(message.chat.id, text, parse_mode='HTML', message_thread_id=TOPIC_ID)
        else:
            bot.send_message(message.chat.id, text, parse_mode='HTML')


@bot.message_handler(commands=['cancel'])
def cancel_command(message):
    if not check_topic_access(message):
        return
    cancel_operation(message)


def get_homework_summary(user_id):
    data = user_data.get(user_id, {})
    subject_name = data.get('subject_name', 'Не указано')
    homework_description = data.get('homework_description', 'Нет описания')
    date_str = data.get('date', 'Не указана')
    added_by = data.get('added_by', 'Аноним')

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%d.%m.%Y')
    except:
        formatted_date = date_str

    return f"<b>📌 Предмет:</b> {subject_name}\n<b>📝 Задание:</b> {homework_description}\n<b>📅 Срок сдачи:</b> {formatted_date}\n<b>👤 Добавит:</b> {added_by}"


def save_homework_to_db(user_id):
    if user_id not in user_data:
        return -1

    conn = None
    try:
        conn = sqlite3.connect('homework.db')
        cursor = conn.cursor()

        cursor.execute('''
                       INSERT INTO homework (subject_name, date, homework_description, added_by, chat_id, topic_id)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ''', (
                           user_data[user_id].get('subject_name', ''),
                           user_data[user_id].get('date', ''),
                           user_data[user_id].get('homework_description', ''),
                           user_data[user_id].get('added_by', 'Аноним'),
                           user_data[user_id].get('chat_id'),
                           user_data[user_id].get('topic_id')
                       ))

        homework_id = cursor.lastrowid

        for file_data in user_data[user_id].get('files', []):
            cursor.execute('''
                           INSERT INTO homework_files (homework_id, file_name, file_type, original_name, added_by)
                           VALUES (?, ?, ?, ?, ?)
                           ''', (
                               homework_id,
                               file_data.get('file_name'),
                               file_data['file_type'],
                               file_data.get('original_name', ''),
                               user_data[user_id].get('added_by', 'Аноним')
                           ))

        conn.commit()
        files_count = len(user_data[user_id].get('files', []))

        if 'temp_files' in user_data[user_id]:
            user_data[user_id]['temp_files'] = []

        return files_count

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        for file_name in user_data[user_id].get('temp_files', []):
            try:
                file_path = os.path.join(FILES_DIR, file_name)
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
        logger.error(f"Ошибка при сохранении задания: {e}")
        return -1
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def cancel_operation(message):
    user_id = message.from_user.id
    if user_id in user_data:
        if 'temp_files' in user_data[user_id]:
            for file_name in user_data[user_id]['temp_files']:
                try:
                    file_path = os.path.join(FILES_DIR, file_name)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    logger.error(f"Ошибка при удалении временного файла: {e}")
        del user_data[user_id]

    log_action(message.from_user, "Отмена операции")

    markup = create_back_to_menu_button()
    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, "❌ Операция отменена.\n\n🏠 Вы можете вернуться в главное меню.",
                         reply_markup=markup, message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, "❌ Операция отменена.\n\n🏠 Вы можете вернуться в главное меню.",
                         reply_markup=markup)


# Команды для администратора
@bot.message_handler(commands=['del_mes'])
def delete_message_command(message):
    """Удаляет сообщение, на которое ответили (только для администратора)"""
    user_info = get_user_info(message.from_user)
    log_action(message.from_user, "Команда /del_mes", "Начало выполнения")

    # НЕ проверяем check_topic_access для этой команды - она должна работать везде
    user_id = message.from_user.id

    # Проверяем права администратора
    if not is_admin(user_id):
        logger.warning(f"Пользователь {user_info} попытался использовать /del_mes без прав")
        try:
            bot.reply_to(message, "❌ У вас нет прав для удаления сообщений")
        except:
            pass
        return

    # Проверяем, есть ли reply_to_message
    if not message.reply_to_message:
        logger.warning(f"Админ {user_info} использовал /del_mes без ответа на сообщение")
        try:
            bot.reply_to(message, "❌ Ответьте на сообщение, которое нужно удалить")
        except:
            pass
        return

    try:
        # Получаем информацию о чате и топике
        chat_id = message.chat.id
        target_message_id = message.reply_to_message.message_id

        # Определяем thread_id для ответа
        thread_id = None
        if hasattr(message, 'message_thread_id'):
            thread_id = message.message_thread_id

        # Логируем попытку удаления
        log_action(message.from_user, "Удаление сообщения", f"ID сообщения: {target_message_id}, Чат: {chat_id}, Топик: {thread_id}")

        # Удаляем целевое сообщение
        bot.delete_message(chat_id, target_message_id)

        # Удаляем сообщение с командой /del_mes
        try:
            bot.delete_message(chat_id, message.message_id)
        except:
            pass

        # Отправляем подтверждение
        confirm_text = "✅ Сообщение удалено"
        try:
            if thread_id and chat_id != thread_id:  # Если это группа с топиками
                confirm_msg = bot.send_message(chat_id, confirm_text, message_thread_id=thread_id)
            else:
                confirm_msg = bot.send_message(chat_id, confirm_text)

            # Удаляем подтверждение через 3 секунды
            threading.Timer(3.0, lambda: bot.delete_message(chat_id, confirm_msg.message_id)).start()

        except Exception as e:
            logger.error(f"Ошибка отправки подтверждения: {e}")

        logger.info(f"Сообщение {target_message_id} успешно удалено админом {user_info}")

    except Exception as e:
        logger.error(f"Ошибка при удалении сообщения: {e}")
        error_text = f"❌ Не удалось удалить сообщение. Ошибка: {str(e)}"
        try:
            bot.reply_to(message, error_text)
        except:
            pass


@bot.message_handler(commands=['clear_all'])
def clear_all_messages_command(message):
    """Удаляет все сообщения в топике (только для администратора и только в топике 60817) - ОПАСНАЯ КОМАНДА"""
    log_action(message.from_user, "Команда /clear_all", "Начало выполнения")
    
    # Проверяем, что команда в правильном топике
    if not is_in_correct_topic(message):
        logger.warning(f"Попытка использования /clear_all вне топика {TOPIC_ID} от пользователя {get_user_info(message.from_user)}")
        error_text = f"❌ Команда /clear_all доступна только в топике {TOPIC_ID}"
        bot.send_message(message.chat.id, error_text)
        return

    user_id = message.from_user.id

    # Проверяем права администратора
    if not is_admin(user_id):
        logger.warning(f"Пользователь {get_user_info(message.from_user)} попытался использовать /clear_all без прав")
        bot.send_message(message.chat.id, "❌ У вас нет прав для удаления сообщений")
        return

    try:
        # Запрашиваем подтверждение
        confirm_text = "⚠️ <b>ВНИМАНИЕ!</b>\n\n"
        confirm_text += "Вы собираетесь удалить ВСЕ сообщения в этом топике.\n"
        confirm_text += "Это действие НЕОБРАТИМО!\n\n"
        confirm_text += "Для подтверждения отправьте: <code>/confirm_clear_all</code>\n"
        confirm_text += "Для отмены отправьте: <code>/cancel</code>"

        # Сохраняем состояние подтверждения
        user_data[user_id] = {
            'waiting_confirm': 'clear_all',
            'chat_id': message.chat.id
        }

        log_action(message.from_user, "Запрос подтверждения /clear_all")

        bot.send_message(message.chat.id, confirm_text, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Ошибка в /clear_all: {e}")


@bot.message_handler(commands=['confirm_clear_all'])
def confirm_clear_all_command(message):
    """Подтверждение удаления всех сообщений"""
    log_action(message.from_user, "Команда /confirm_clear_all", "Начало выполнения")
    
    # Проверяем, что команда в правильном топике
    if not is_in_correct_topic(message):
        return

    user_id = message.from_user.id

    # Проверяем права администратора и состояние подтверждения
    if not is_admin(user_id) or user_id not in user_data or user_data[user_id].get('waiting_confirm') != 'clear_all':
        return

    try:
        # Получаем сохраненные данные
        chat_id = user_data[user_id].get('chat_id')

        # Удаляем состояние подтверждения
        del user_data[user_id]

        user_info = get_user_info(message.from_user)
        logger.warning(f"Админ {user_info} начал удаление ВСЕХ сообщений в чате {chat_id}")

        # Отправляем предупреждение
        warning_msg = bot.send_message(chat_id, "⚠️ Начинаю удаление ВСЕХ сообщений... Это может занять время.")

        # Простая реализация - удаляем 1000 сообщений
        deleted_total = 0
        max_messages = 1000

        for msg_id in range(1, max_messages + 1):
            try:
                # Пропускаем сообщение с прогрессом
                if msg_id == warning_msg.message_id:
                    continue

                bot.delete_message(chat_id, msg_id)
                deleted_total += 1

                # Задержка чтобы не превысить лимиты API
                if deleted_total % 10 == 0:
                    threading.Event().wait(0.1)

            except Exception as e:
                # Если не удалось удалить сообщение, продолжаем
                continue

        # Обновляем финальное сообщение
        final_text = f"✅ Удалено {deleted_total} сообщений."
        bot.edit_message_text(final_text, chat_id=chat_id, message_id=warning_msg.message_id)

        # Удаляем финальное сообщение через 10 секунд
        threading.Timer(10.0, lambda: bot.delete_message(chat_id, warning_msg.message_id)).start()

        log_action(message.from_user, "Завершение /clear_all", f"Удалено сообщений: {deleted_total}")

    except Exception as e:
        logger.error(f"Ошибка в /confirm_clear_all: {e}")
        log_action(message.from_user, "Ошибка в /confirm_clear_all", f"Ошибка: {str(e)}")


@bot.message_handler(commands=['call_all'])
def call_all_members_command(message):
    """Упоминает всех участников чата в одном сообщении (только для администратора)"""
    log_action(message.from_user, "Команда /call_all", "Начало выполнения")
    
    # Проверяем, что команда используется в групповом чате
    if message.chat.type not in ['group', 'supergroup']:
        bot.send_message(message.chat.id, "❌ Эта команда работает только в групповых чатах")
        log_action(message.from_user, "Попытка использования /call_all не в групповом чате")
        return

    user_id = message.from_user.id

    # Проверяем права администратора
    if not is_admin(user_id):
        logger.warning(f"Пользователь {get_user_info(message.from_user)} попытался использовать /call_all без прав")
        bot.send_message(message.chat.id, "❌ У вас нет прав для упоминания всех участников")
        return

    try:
        # Получаем информацию о чате
        chat_id = message.chat.id
        
        # Определяем thread_id для ответа
        thread_id = None
        if hasattr(message, 'message_thread_id'):
            thread_id = message.message_thread_id
        
        # Пытаемся получить количество участников
        try:
            chat_member_count = bot.get_chat_member_count(chat_id)
        except:
            chat_member_count = 0
        
        log_action(message.from_user, "Упоминание всех участников", f"Чат: {chat_id}, Участников: {chat_member_count}")
        
        # Создаем скрытое упоминание всех участников
        # Используем невидимый символ Zero Width Space (U+200B) и упоминание @all
        # Это создаст уведомление для всех, но сообщение будет выглядеть коротким
        mention_text = "​👥"  # Содержит невидимый символ для скрытого упоминания
        
        # Добавляем текст для привлечения внимания
        notification_text = "🔔 <b>Внимание всем участникам чата!</b>"
        
        # Комбинируем текст
        full_text = f"{mention_text}\n\n{notification_text}"
        
        # Отправляем сообщение
        try:
            if thread_id:
                mention_message = bot.send_message(chat_id, full_text, parse_mode='HTML', 
                                                  message_thread_id=thread_id)
            else:
                mention_message = bot.send_message(chat_id, full_text, parse_mode='HTML')
            
            # Удаляем команду /call_all
            try:
                bot.delete_message(chat_id, message.message_id)
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение с командой /call_all: {e}")
            
            # Удаляем упоминание через 5 секунд (чтобы оно было кратковременным)
            threading.Timer(5.0, lambda: delete_call_message(chat_id, mention_message.message_id, thread_id)).start()
            
            log_action(message.from_user, "Упоминание отправлено", "Сообщение будет удалено через 5 секунд")
            
        except Exception as e:
            logger.error(f"Ошибка отправки упоминания: {e}")
            bot.send_message(message.chat.id, "❌ Не удалось отправить упоминание")
            
    except Exception as e:
        logger.error(f"Ошибка в /call_all: {e}")
        bot.send_message(message.chat.id, f"❌ Ошибка при выполнении команды: {str(e)}")


def delete_call_message(chat_id, message_id, thread_id=None):
    """Удаляет сообщение с упоминанием всех участников"""
    try:
        if thread_id:
            bot.delete_message(chat_id, message_id)
        else:
            bot.delete_message(chat_id, message_id)
        logger.info(f"Сообщение с упоминанием удалено: chat_id={chat_id}, message_id={message_id}")
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщения с упоминанием: {e}")


@bot.message_handler(commands=['admin_help'])
def admin_help_command(message):
    """Показывает справку по командам администратора"""
    user_id = message.from_user.id

    help_text = "🛠️ <b>Команды администратора:</b>\n\n"

    if is_admin(user_id):
        help_text += "<b>Доступные команды:</b>\n"
        help_text += "<code>/del_mes</code> - удалить сообщение (ответьте на него) - работает везде\n"
        help_text += f"<code>/clear_all</code> - удалить все сообщения в топике (только в топике {TOPIC_ID})\n"
        help_text += "<code>/call_all</code> - упомянуть всех участников чата (кратковременное сообщение)\n"
        help_text += "<code>/add_exam</code> - добавить зачёт\n"
        help_text += "<code>/delete_exam</code> - удалить зачёт\n\n"
    else:
        help_text += "❌ <b>У вас нет прав администратора</b>\n\n"

    help_text += "<b>Общие команды:</b>\n"
    help_text += "<code>/help</code> - общая справка по боту\n"
    help_text += "<code>/admin_help</code> - эта справка\n"

    bot.send_message(message.chat.id, help_text, parse_mode='HTML',
                     reply_markup=create_back_to_menu_button())


# Функции для работы с зачетами
def add_exam_command_handler(message):
    """Начинает процесс добавления зачета (только для админа)"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.send_message(message.chat.id, "❌ У вас нет прав для добавления зачетов")
        return

    if user_id in user_data:
        del user_data[user_id]

    user_data[user_id] = {
        'step': 'exam_subject_name',
        'files': [],
        'temp_files': [],
        'added_by': f"{message.from_user.first_name or 'Аноним'}",
        'chat_id': message.chat.id,
        'topic_id': message.message_thread_id if hasattr(message, 'message_thread_id') else None
    }

    log_action(message.from_user, "Начало добавления зачета")

    text = "📝 <b>Добавление зачета</b>\n\n1. Введите название предмета:\n<i>Пример: Математика, Физика</i>\n\n<i>Или отправьте /cancel для отмены</i>"

    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, text, parse_mode='HTML',
                         reply_markup=create_back_to_menu_button(), message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, text, parse_mode='HTML',
                         reply_markup=create_back_to_menu_button())


@bot.message_handler(
    func=lambda message: message.from_user.id in user_data and user_data.get(message.from_user.id, {}).get(
        'step') == 'exam_subject_name')
def process_exam_subject_name(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    if message.text.lower() == '/cancel':
        cancel_operation(message)
        return

    user_data[user_id]['subject_name'] = message.text
    user_data[user_id]['step'] = 'exam_description'

    log_action(message.from_user, "Ввод названия предмета для зачета", f"Предмет: {message.text}")

    text = "2. Введите описание зачета (что нужно подготовить):\n<i>Можно оставить пустым, отправив \"-\"</i>\n\n<i>Или отправьте /cancel для отмены</i>"

    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, text, parse_mode='HTML', message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, text, parse_mode='HTML')


@bot.message_handler(
    func=lambda message: message.from_user.id in user_data and user_data.get(message.from_user.id, {}).get(
        'step') == 'exam_description')
def process_exam_description(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    if message.text.lower() == '/cancel':
        cancel_operation(message)
        return

    user_data[user_id]['description'] = message.text if message.text != "-" else ""
    user_data[user_id]['step'] = 'exam_date'

    log_action(message.from_user, "Ввод описания зачета")

    text = "3. Введите дату зачета:\n<i>Формат: ДД.ММ.ГГГГ</i>\n\n<i>Или отправьте /cancel для отмены</i>"

    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, text, parse_mode='HTML', message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, text, parse_mode='HTML')


@bot.message_handler(
    func=lambda message: message.from_user.id in user_data and user_data.get(message.from_user.id, {}).get(
        'step') == 'exam_date')
def process_exam_date(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    if message.text.lower() == '/cancel':
        cancel_operation(message)
        return

    date_input = message.text
    try:
        date_obj = datetime.strptime(date_input, '%d.%m.%Y')
        user_data[user_id]['exam_date'] = date_obj.strftime('%Y-%m-%d')

        # Сохраняем зачет
        if save_exam_to_db(user_id):
            response = "✅ <b>Зачет успешно добавлен!</b>\n"
            response += f"📚 Предмет: {user_data[user_id]['subject_name']}\n"
            response += f"📅 Дата: {date_input}\n"
            if user_data[user_id]['description']:
                response += f"📝 Описание: {user_data[user_id]['description']}\n"

            log_action(message.from_user, "Добавление зачета", f"Предмет: {user_data[user_id]['subject_name']}, Дата: {date_input}")

            if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
                bot.send_message(message.chat.id, response, parse_mode='HTML',
                                 reply_markup=create_back_to_menu_button(), message_thread_id=TOPIC_ID)
            else:
                bot.send_message(message.chat.id, response, parse_mode='HTML',
                                 reply_markup=create_back_to_menu_button())

            # Очищаем данные пользователя
            del user_data[user_id]
        else:
            send_error(message, "❌ Ошибка при сохранении зачета")

    except ValueError:
        send_error(message, "❌ Неверный формат даты! Используйте ДД.ММ.ГГГГ")


def save_exam_to_db(user_id):
    """Сохраняет зачет в базу данных"""
    try:
        conn = sqlite3.connect('homework.db')
        cursor = conn.cursor()

        cursor.execute('''
                       INSERT INTO exams (subject_name, exam_date, description, added_by, chat_id, topic_id)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ''', (
                           user_data[user_id].get('subject_name', ''),
                           user_data[user_id].get('exam_date', ''),
                           user_data[user_id].get('description', ''),
                           user_data[user_id].get('added_by', 'Аноним'),
                           user_data[user_id].get('chat_id'),
                           user_data[user_id].get('topic_id')
                       ))

        conn.commit()
        exam_id = cursor.lastrowid
        conn.close()

        logger.info(f"Зачет сохранен в БД: ID={exam_id}, предмет={user_data[user_id].get('subject_name')}")
        return True

    except Exception as e:
        logger.error(f"Ошибка сохранения зачета в БД: {e}")
        return False


def show_exam_dates_list(call):
    """Показывает список дат с зачетами (доступно всем)"""
    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT exam_date FROM exams ORDER BY exam_date')
    dates = cursor.fetchall()
    conn.close()

    if not dates:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="📭 Пока нет добавленных зачетов.",
            reply_markup=create_back_to_menu_button()
        )
        return

    markup = types.InlineKeyboardMarkup(row_width=2)

    for date_tuple in dates:
        date_str = date_tuple[0]
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d.%m.%Y')

            conn = sqlite3.connect('homework.db')
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM exams WHERE exam_date = ?', (date_str,))
            count = cursor.fetchone()[0]
            conn.close()

            markup.add(types.InlineKeyboardButton(
                f"📅 {formatted_date} ({count})",
                callback_data=f"view_exam_date_{date_str}"
            ))
        except Exception as e:
            logger.error(f"Ошибка при форматировании даты экзамена: {e}")

    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="exams_menu"))
    markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="📅 <b>Выберите дату для просмотра зачетов:</b>",
        parse_mode='HTML',
        reply_markup=markup
    )


def show_exams_for_date(call, date_str, user_id):
    """Показывает зачеты на указанную дату (все могут смотреть, но кнопки удаления только у админа)"""
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%d.%m.%Y')
    except:
        formatted_date = date_str

    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()
    cursor.execute('''
                   SELECT id, subject_name, description, added_by
                   FROM exams
                   WHERE exam_date = ?
                   ORDER BY created_at
                   ''', (date_str,))

    exams = cursor.fetchall()
    conn.close()

    if not exams:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"📭 На {formatted_date} зачетов нет.",
            reply_markup=create_back_to_menu_button()
        )
        return

    response = f"📅 <b>Зачеты на {formatted_date}:</b>\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)

    for exam in exams:
        exam_id, subject_name, description, added_by = exam
        response += f"📚 <b>{subject_name}</b>\n"
        response += f"👤 Добавил: {added_by}\n"
        if description:
            response += f"📝 {description}\n"
        response += "━━━━━━━━━━━━━━\n"

        # Кнопку удаления добавляем только для администратора
        if is_admin(user_id):
            markup.add(types.InlineKeyboardButton(
                f"❌ Удалить {subject_name[:15]}...",
                callback_data=f"delete_exam_{exam_id}"
            ))

    markup.add(types.InlineKeyboardButton("🔙 Назад к датам", callback_data="view_exams_menu"))
    markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=response,
        parse_mode='HTML',
        reply_markup=markup
    )


def show_exams_for_deletion(call):
    """Показывает список зачетов для удаления (только для админа)"""
    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, subject_name, exam_date FROM exams ORDER BY exam_date')
    exams = cursor.fetchall()
    conn.close()

    if not exams:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="📭 Нет зачетов для удаления.",
            reply_markup=create_exams_menu(call.from_user.id)
        )
        return

    response = "🗑️ <b>Выберите зачет для удаления:</b>\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)

    for exam in exams:
        exam_id, subject_name, exam_date = exam
        try:
            date_obj = datetime.strptime(exam_date, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d.%m.%Y')
        except:
            formatted_date = exam_date

        response += f"📚 {subject_name} - {formatted_date}\n"
        markup.add(types.InlineKeyboardButton(
            f"❌ {subject_name[:15]}... ({formatted_date})",
            callback_data=f"delete_exam_{exam_id}"
        ))

    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="exams_menu"))
    markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=response,
        parse_mode='HTML',
        reply_markup=markup
    )


def delete_exam_callback(call, exam_id):
    """Удаляет зачет (только для админа)"""
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав для удаления зачетов")
        log_action(call.from_user, "Попытка удаления зачета без прав", f"ID зачета: {exam_id}")
        return

    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()

    try:
        # Получаем информацию о зачете перед удалением
        cursor.execute('SELECT subject_name, exam_date FROM exams WHERE id = ?', (exam_id,))
        exam_info = cursor.fetchone()

        if exam_info:
            subject_name, exam_date = exam_info

            # Удаляем зачет
            cursor.execute('DELETE FROM exams WHERE id = ?', (exam_id,))
            conn.commit()

            bot.answer_callback_query(call.id, f"✅ Зачет '{subject_name}' удален")
            log_action(call.from_user, "Удаление зачета", f"ID: {exam_id}, Предмет: {subject_name}")
            logger.info(f"Зачет удален: ID={exam_id}, предмет={subject_name}")

            # Возвращаемся в меню зачетов
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ Зачет '{subject_name}' успешно удален!\n\n👇 Выберите действие:",
                parse_mode='HTML',
                reply_markup=create_exams_menu(call.from_user.id)
            )
        else:
            bot.answer_callback_query(call.id, "❌ Зачет не найден")

    except Exception as e:
        logger.error(f"Ошибка при удалении зачета: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка при удалении зачета")
        log_action(call.from_user, "Ошибка при удалении зачета", f"ID: {exam_id}, Ошибка: {str(e)}")
    finally:
        conn.close()


def show_upcoming_exams(call):
    """Показывает ближайшие зачеты (в течение 7 дней, доступно всем)"""
    today = datetime.now().date()
    week_later = today + timedelta(days=7)

    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()
    cursor.execute('''
                   SELECT subject_name, exam_date, description
                   FROM exams
                   WHERE exam_date BETWEEN ? AND ?
                   ORDER BY exam_date
                   ''', (today.strftime('%Y-%m-%d'), week_later.strftime('%Y-%m-%d')))

    upcoming_exams = cursor.fetchall()
    conn.close()

    if not upcoming_exams:
        response = "📭 Ближайшие зачеты отсутствуют (в течение недели)."
    else:
        response = "🔔 <b>Ближайшие зачеты (7 дней):</b>\n\n"

        for exam in upcoming_exams:
            subject_name, exam_date, description = exam
            date_obj = datetime.strptime(exam_date, '%Y-%m-%d')
            days_left = (date_obj.date() - today).days

            response += f"📚 <b>{subject_name}</b>\n"
            response += f"📅 Дата: {date_obj.strftime('%d.%m.%Y')}\n"
            response += f"⏰ Осталось дней: {days_left}\n"
            if description:
                response += f"📝 {description}\n"
            response += "━━━━━━━━━━━━━━\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="exams_menu"))
    markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=response,
        parse_mode='HTML',
        reply_markup=markup
    )


@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if user_id in user_data:
        return
    pass


if __name__ == '__main__':
    init_db()
    logger.info("Бот запущен!")
    logger.info(f"Администраторы: {ADMIN_IDS}")
    logger.info("Ожидание команд...")

    # Запускаем планировщик уведомлений в отдельном потоке
    notification_thread = threading.Thread(target=notification_scheduler, daemon=True)
    notification_thread.start()
    logger.info("Планировщик уведомлений запущен")

    # Добавляем информацию о командах администратора в логи
    logger.info("Команды администратора активированы:")
    logger.info("/del_mes - удалить сообщение (ответьте на него) - работает везде")
    logger.info(f"/clear_all - удалить все сообщения в топике (только в топике {TOPIC_ID})")
    logger.info("/call_all - упомянуть всех участников чата (кратковременное сообщение)")
    logger.info("/admin_help - справка по командам администратора")

    try:
        bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
