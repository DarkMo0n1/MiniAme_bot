import sqlite3
import os
import uuid
from datetime import datetime, timedelta
import telebot
from telebot import types
import threading
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = '8549158268:AAHmfHcRnUpTxilyY72RL8pWK9Fr7qTcKBU'
bot = telebot.TeleBot(TOKEN)

# Абсолютные пути для VPS
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILES_DIR = os.path.join(BASE_DIR, 'homework_files')
if not os.path.exists(FILES_DIR):
    os.makedirs(FILES_DIR, exist_ok=True)
    logger.info(f"Создана директория для файлов: {FILES_DIR}")

TOPIC_ID = 60817
CONSOLE_CHAT_ID = -1002530863470
BIRTHDAYS_FILE = os.path.join(BASE_DIR, 'birthdays.txt')

user_data = {}


def console_input():
    print("\nКонсольный режим бота активирован!")
    print("Введите сообщение, начиная с '!', чтобы отправить его от лица бота")
    print("Для выхода введите 'exit'\n")

    while True:
        try:
            user_input = input("> ").strip()

            if user_input.lower() == 'exit':
                print("Завершение работы...")
                os._exit(0)

            elif user_input.startswith('!'):
                message_text = user_input[1:].strip()
                if not message_text:
                    print("Сообщение не может быть пустым!")
                    continue

                if CONSOLE_CHAT_ID:
                    try:
                        bot.send_message(CONSOLE_CHAT_ID, message_text)
                        print(f"✓ Сообщение отправлено в чат {CONSOLE_CHAT_ID}")
                    except Exception as e:
                        print(f"✗ Ошибка отправки: {e}")
                else:
                    print("✗ Не указан ID чата. Отправьте сначала любое сообщение боту.")

            else:
                print("Для отправки сообщения начните его с '!'")

        except KeyboardInterrupt:
            print("\nЗавершение работы...")
            os._exit(0)
        except Exception as e:
            print(f"Ошибка: {e}")


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


def init_db():
    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS homework (
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

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS homework_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            homework_id INTEGER,
            file_name TEXT NOT NULL,  -- Только имя файла, без пути
            file_type TEXT NOT NULL,
            original_name TEXT,
            added_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (homework_id) REFERENCES homework(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS birthdays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            month INTEGER NOT NULL CHECK (month >= 1 AND month <= 12),
            day INTEGER NOT NULL CHECK (day >= 1 AND day <= 31),
            added_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Обновляем структуру таблицы homework_files
    cursor.execute("PRAGMA table_info(homework_files)")
    columns = [column[1] for column in cursor.fetchall()]
    
    # Переименовываем file_path в file_name если нужно
    if 'file_path' in columns:
        cursor.execute('ALTER TABLE homework_files RENAME COLUMN file_path TO file_name')
    
    # Добавляем original_name если нет
    if 'original_name' not in columns:
        cursor.execute('ALTER TABLE homework_files ADD COLUMN original_name TEXT')

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
    save_birthdays_to_db()
    logger.info("База данных инициализирована")


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
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('📚 ДЗ', callback_data='homework_submenu'),
        types.InlineKeyboardButton('👨‍🏫 Учителя', callback_data='teacher_name_menu'),
        types.InlineKeyboardButton('🎂 Дни рождения', callback_data='birthdays_menu'),
        types.InlineKeyboardButton('ℹ️ Помощь', callback_data='help_menu')
    )
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


def check_topic_access(message):
    if TOPIC_ID is None:
        return True
    if message.chat.type in ['group', 'supergroup']:
        if hasattr(message, 'message_thread_id'):
            return message.message_thread_id == TOPIC_ID
    return False


@bot.message_handler(commands=['start'])
def send_welcome(message):
    global CONSOLE_CHAT_ID
    CONSOLE_CHAT_ID = message.chat.id
    logger.info(f"ID чата: {CONSOLE_CHAT_ID}")

    if not check_topic_access(message):
        return

    help_text = "👋 Привет! Я бот для управления домашними заданиями.\n\n👇 <b>Выберите действие:</b>"

    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, help_text, parse_mode='HTML',
                        reply_markup=create_main_menu(), message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, help_text, parse_mode='HTML',
                        reply_markup=create_main_menu())


@bot.message_handler(commands=['help'])
def help_command(message):
    if not check_topic_access(message):
        return

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

💡 <b>Особенности:</b>
• Все задания общие для всех
• Можно прикреплять несколько файлов
• Для завершения добавления файлов отправьте <code>/done</code>
• Для пропуска отправьте <code>/skip</code>
• Задания может удалить любой пользователь
    """

    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, help_text, parse_mode='HTML',
                        reply_markup=create_back_to_menu_button(), message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, help_text, parse_mode='HTML',
                        reply_markup=create_back_to_menu_button())


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

    text = "📝 <b>Добавление домашнего задания</b>\n\n1. Введите название предмета:\n<i>Пример: Математика, Физика</i>\n\n<i>Или отправьте /cancel для отмены</i>"

    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, text, parse_mode='HTML',
                        reply_markup=create_back_to_menu_button(), message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, text, parse_mode='HTML',
                        reply_markup=create_back_to_menu_button())


@bot.message_handler(func=lambda message: message.from_user.id in user_data and user_data.get(message.from_user.id, {}).get('step') == 'subject_name')
def process_subject_name(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if message.text.lower() == '/cancel':
        cancel_operation(message)
        return

    user_data[user_id]['subject_name'] = message.text
    user_data[user_id]['step'] = 'homework_description'

    text = "2. Введите описание домашнего задания:\n<i>Можно оставить пустым, отправив \"-\"</i>\n\n<i>Или отправьте /cancel для отмены</i>"

    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, text, parse_mode='HTML', message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, text, parse_mode='HTML')


@bot.message_handler(func=lambda message: message.from_user.id in user_data and user_data.get(message.from_user.id, {}).get('step') == 'homework_description')
def process_homework_description(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if message.text.lower() == '/cancel':
        cancel_operation(message)
        return

    user_data[user_id]['homework_description'] = message.text if message.text != "-" else ""
    user_data[user_id]['step'] = 'date'

    text = "3. Введите дату сдачи задания:\n<i>Формат: ДД.ММ.ГГГГ или сегодня/завтра/послезавтра</i>\n\n<i>Или отправьте /cancel для отмены</i>"

    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, text, parse_mode='HTML', message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, text, parse_mode='HTML')


@bot.message_handler(func=lambda message: message.from_user.id in user_data and user_data.get(message.from_user.id, {}).get('step') == 'date')
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

        if chat_id and TOPIC_ID is not None:
            bot.send_message(chat_id, text, parse_mode='HTML', message_thread_id=TOPIC_ID)
        else:
            bot.send_message(chat_id, text, parse_mode='HTML')

    elif call.data == 'save_without_file':
        bot.answer_callback_query(call.id)
        files_count = save_homework_to_db(user_id)
        text = "✅ <b>Домашнее задание успешно сохранено без файла!</b>" if files_count >= 0 else "❌ <b>Ошибка при сохранении задания!</b>"
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
        row = subjects[i:i+3]
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

💡 <b>Особенности:</b>
• Все задания общие для всех
• Можно прикреплять несколько файлов
• Для завершения добавления файлов отправьте <code>/done</code>
• Для пропуска отправьте <code>/skip</code>
• Задания может удалить любой пользователь
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
            elif files_count == 0:
                response = "✅ <b>Домашнее задание успешно сохранено без файлов!</b>"
            else:
                response = "❌ <b>Ошибка при сохранении задания!</b>"

            if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
                bot.send_message(message.chat.id, response + "\n\n🏠 Вы можете вернуться в главное меню:",
                                parse_mode='HTML', reply_markup=create_back_to_menu_button(), message_thread_id=TOPIC_ID)
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

            buttons.append(types.InlineKeyboardButton(f"📅 {formatted_date} ({count})", callback_data=f"view_date_{date_str}"))
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

    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()

    if chat_id:
        cursor.execute('''
            SELECT h.id, h.subject_name, h.homework_description, h.added_by, COUNT(f.id) as file_count
            FROM homework h LEFT JOIN homework_files f ON h.id = f.homework_id
            WHERE h.date = ? AND h.chat_id = ?
            GROUP BY h.id, h.subject_name, h.homework_description, h.added_by
            ORDER BY h.created_at
        ''', (date_str, chat_id))
    else:
        cursor.execute('''
            SELECT h.id, h.subject_name, h.homework_description, h.added_by, COUNT(f.id) as file_count
            FROM homework h LEFT JOIN homework_files f ON h.id = f.homework_id
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

    markup = types.InlineKeyboardMarkup(row_width=1)
    for hw in homework_list:
        hw_id, subject_name, _, _, file_count = hw
        short_name = subject_name[:15] + "..." if len(subject_name) > 15 else subject_name

        row_buttons = []
        if file_count > 0:
            row_buttons.append(types.InlineKeyboardButton(f"📁 {short_name}", callback_data=f"view_files_{hw_id}"))
        row_buttons.append(types.InlineKeyboardButton(f"❌ {short_name}", callback_data=f"delete_{hw_id}"))
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

    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()

    cursor.execute('SELECT subject_name, homework_description, added_by FROM homework WHERE id = ?', (hw_id,))
    hw_info = cursor.fetchone()

    if not hw_info:
        bot.answer_callback_query(call.id, "❌ Задание не найдено")
        return

    subject_name, homework_description, added_by = hw_info
    cursor.execute('SELECT file_name, file_type, original_name, added_by FROM homework_files WHERE homework_id = ?', (hw_id,))
    files = cursor.fetchall()
    conn.close()

    if not files:
        bot.answer_callback_query(call.id, "❌ У этого задания нет файлов")
        return

    bot.answer_callback_query(call.id)
    response = f"📁 <b>Файлы к заданию:</b> {subject_name}\n<b>👤 Добавил:</b> {added_by}\n"
    if homework_description:
        response += f"<b>Описание:</b> {homework_description}\n"
    response += f"\n<b>Всего файлов:</b> {len(files)}\n\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад к заданиям", callback_data="back_to_dates"))
    markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))

    if chat_id and TOPIC_ID is not None:
        bot.send_message(chat_id, response, parse_mode='HTML', reply_markup=markup, message_thread_id=TOPIC_ID)
    else:
        bot.send_message(chat_id, response, parse_mode='HTML', reply_markup=markup)

    for i, (file_name, file_type, original_name, file_added_by) in enumerate(files, 1):
        try:
            # Формируем полный путь к файлу
            file_path = os.path.join(FILES_DIR, file_name)
            
            if os.path.exists(file_path):
                logger.info(f"Отправка файла: {file_path}")
                with open(file_path, 'rb') as file:
                    file_data = file.read()
                    caption = f"📄 Файл {i}: {original_name or file_name}"
                    if file_added_by:
                        caption += f"\n👤 Добавил: {file_added_by}"

                    # Определяем функцию для отправки файла
                    send_func = None
                    params = {}
                    
                    if file_type == 'фото':
                        send_func = bot.send_photo
                        params = {'caption': caption}
                    elif file_type == 'документ':
                        send_func = bot.send_document
                        params = {'caption': caption, 'visible_file_name': original_name or file_name}
                    elif file_type == 'аудио':
                        send_func = bot.send_audio
                        params = {'caption': caption, 'title': original_name or file_name}
                    elif file_type == 'видео':
                        send_func = bot.send_video
                        params = {'caption': caption}
                    elif file_type == 'голосовое сообщение':
                        send_func = bot.send_voice
                        params = {'caption': caption}
                    
                    if send_func:
                        if chat_id and TOPIC_ID is not None:
                            send_func(chat_id, file_data, message_thread_id=TOPIC_ID, **params)
                        else:
                            send_func(chat_id, file_data, **params)
                    else:
                        send_error_file(chat_id, f"❌ Неподдерживаемый тип файла: {original_name}")
            else:
                logger.error(f"Файл не найден: {file_path}")
                send_error_file(chat_id, f"❌ Файл не найден: {original_name}")

        except Exception as e:
            logger.error(f"Ошибка при отправке файла {i}: {e}")
            send_error_file(chat_id, f"❌ Не удалось отправить файл {i}: {original_name}")


def send_error_file(chat_id, text):
    if chat_id and TOPIC_ID is not None:
        bot.send_message(chat_id, text, message_thread_id=TOPIC_ID)
    else:
        bot.send_message(chat_id, text)


def delete_homework_callback(call):
    hw_id = int(call.data.replace('delete_', ''))
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT subject_name, date FROM homework WHERE id = ?', (hw_id,))
        hw_info = cursor.fetchone()

        if not hw_info:
            bot.answer_callback_query(call.id, "❌ Задание не найдено")
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


@bot.message_handler(commands=['teacher_name'])
def subject(message):
    if not check_topic_access(message):
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    subjects = ['Математика', 'Информатика', 'Физика', 'История', 'Биология', 'ОБЖ',
               'Химия', 'Литература', 'Русский', 'Английский', 'Физра', 'ВВС', 'Общество']

    for i in range(0, len(subjects), 3):
        row = subjects[i:i+3]
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

    text = "🎂 <b>Добавление дня рождения</b>\n\n1. Введите имя одногруппника:\n<i>Пример: Иванов Иван</i>\n\n<i>Или отправьте /cancel для отмены</i>"

    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, text, parse_mode='HTML',
                        reply_markup=create_back_to_menu_button(), message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, text, parse_mode='HTML',
                        reply_markup=create_back_to_menu_button())


@bot.message_handler(func=lambda message: message.from_user.id in user_data and user_data.get(message.from_user.id, {}).get('step') == 'birthday_name')
def process_birthday_name(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if message.text.lower() == '/cancel':
        cancel_operation(message)
        return

    user_data[user_id]['birthday_data']['name'] = message.text
    user_data[user_id]['step'] = 'birthday_month'

    text = "2. Введите месяц рождения (число от 1 до 12):\n<i>Пример: 1 (для января), 12 (для декабря)</i>\n\n<i>Или отправьте /cancel для отмены</i>"

    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, text, parse_mode='HTML', message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, text, parse_mode='HTML')


@bot.message_handler(func=lambda message: message.from_user.id in user_data and user_data.get(message.from_user.id, {}).get('step') == 'birthday_month')
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


@bot.message_handler(func=lambda message: message.from_user.id in user_data and user_data.get(message.from_user.id, {}).get('step') == 'birthday_day')
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

    markup = create_back_to_menu_button()
    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, "❌ Операция отменена.\n\n🏠 Вы можете вернуться в главное меню.",
                        reply_markup=markup, message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, "❌ Операция отменена.\n\n🏠 Вы можете вернуться в главное меню.",
                        reply_markup=markup)


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
    print("Бот запущен!")
    console_thread = threading.Thread(target=console_input, daemon=True)
    console_thread.start()
    bot.polling(none_stop=True)
