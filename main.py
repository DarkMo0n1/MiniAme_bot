import sqlite3
import os
import uuid
from datetime import datetime, timedelta
import telebot
from telebot import types
import threading
import logging
import pytz
from pytz import timezone

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
REFERENCE_FILES_DIR = os.path.join(BASE_DIR, 'reference_files')

# Создаем директории если их нет
for directory in [FILES_DIR, EXAM_FILES_DIR, REFERENCE_FILES_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Создана директория: {directory}")

# Константы
TOPIC_ID = 60817
CONSOLE_CHAT_ID = -1002530863470
NOTIFICATION_CHAT_ID = 2
ADMIN_IDS = [1087190562, 5621181751, 2068653336]
BIRTHDAYS_FILE = os.path.join(BASE_DIR, 'birthdays.txt')
MOSCOW_TZ = timezone('Europe/Moscow')
BIRTHDAY_WISH_TIME = 9

# Глобальные переменные
user_data = {}
exam_notifications = {}

# Импорт функций из других модулей
from database import init_db, save_birthdays_to_db, load_birthdays, add_birthday_to_file
from keyboards import create_main_menu, create_back_to_menu_button
from notifications import notification_scheduler
from handlers import *
from reference_system import *
from request_system import *

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
    """Проверяет доступ к топику"""
    if TOPIC_ID is None:
        return True

    if message.chat.type == 'private':
        return True

    if message.chat.type in ['group', 'supergroup']:
        if hasattr(message, 'message_thread_id'):
            return message.message_thread_id == TOPIC_ID
        return True

    return False

def is_in_correct_topic(message):
    """Проверяет, находится ли сообщение в правильном топике"""
    if message.chat.type == 'private':
        return False

    if TOPIC_ID is None:
        return True

    if message.chat.type in ['group', 'supergroup']:
        if hasattr(message, 'message_thread_id'):
            return message.message_thread_id == TOPIC_ID
    return False

# Основные команды
@bot.message_handler(commands=['start'])
def send_welcome(message):
    global CONSOLE_CHAT_ID
    CONSOLE_CHAT_ID = message.chat.id
    user_info = get_user_info(message.from_user)
    logger.info(f"Пользователь {user_info} запустил бота в чате {CONSOLE_CHAT_ID}")

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
<code>/check_birthdays</code> - Проверить дни рождения на сегодня
<code>/solution номер</code> - Добавить решение к заданию
<code>/search_reference запрос</code> - Поиск справочных материалов
<code>/my_requests</code> - Мои запросы на добавление файлов
<code>/cancel</code> - Отменить операцию
<code>/help</code> - Справка
<code>/admin_help</code> - Команды администратора
    """

    if is_admin(user_id):
        help_text += "\n\n🛠️ <b>Команды администратора:</b>\n"
        help_text += "<code>/del_mes</code> - удалить сообщение (ответьте на него)\n"
        help_text += f"<code>/clear_all</code> - удалить все сообщения в топике {TOPIC_ID}\n"
        help_text += "<code>/call_all</code> - упомянуть всех участников чата\n"
        help_text += "<code>/set_birthday_time час</code> - установить время отправки поздравлений\n"
        help_text += "<code>/check_birthdays</code> - проверить и отправить поздравления\n"
        help_text += "<b>Для справочных материалов:</b>\n"
        help_text += "<code>/done_reference</code> - завершить добавление файлов в папку\n"
        help_text += "<code>/done_request</code> - завершить создание запроса на добавление\n"

    help_text += """
    
📤 <b>Запросы на добавление файлов:</b>
• Обычные пользователи могут запрашивать добавление файлов в справочные материалы
• Администраторы рассматривают запросы и принимают решение
• Для создания запроса используйте меню справочных материалов
• Для отслеживания статуса используйте <code>/my_requests</code>

📖 <b>Справочные материалы:</b>
• Хранилище конспектов, учебных материалов и справочников
• Материалы организованы по папкам
• Можно запрашивать файлы по диапазону (например, 1-5)
• Для поиска используйте <code>/search_reference запрос</code>

📋 <b>Ближайшие зачеты:</b>
• При добавлении зачета можно прикреплять файлы для подготовки
• Файлы могут быть любого типа (документы, фото, аудио, видео)
• Для завершения добавления файлов используйте <code>/done_exam</code>
• Для пропуска добавления файлов используйте <code>/skip_exam</code>

🎉 <b>Автоматические поздравления:</b>
• Бот автоматически поздравляет с днем рождения в 9:00 по московскому времени
• Для настройки времени используйте команду администратора
• Поздравления отправляются в тот же чат, где находится бот

💡 <b>Особенности:</b>
• Все задания общие для всех
• Можно прикреплять несколько файлов
• Для завершения добавления файлов отправьте <code>/done</code>
• Для пропуска отправьте <code>/skip</code>
• Задания может удалить только администратор
    """

    bot.send_message(message.chat.id, help_text, parse_mode='HTML',
                     reply_markup=create_back_to_menu_button(), message_thread_id=thread_id)

@bot.message_handler(commands=['cancel'])
def cancel_command(message):
    if not check_topic_access(message):
        return
    cancel_operation(message)

# Команды администратора
@bot.message_handler(commands=['del_mes'])
def delete_message_command(message):
    user_info = get_user_info(message.from_user)
    log_action(message.from_user, "Команда /del_mes", "Начало выполнения")

    if not is_admin(message.from_user.id):
        logger.warning(f"Пользователь {user_info} попытался использовать /del_mes без прав")
        try:
            bot.reply_to(message, "❌ У вас нет прав для удаления сообщений")
        except:
            pass
        return

    if not message.reply_to_message:
        logger.warning(f"Админ {user_info} использовал /del_mes без ответа на сообщение")
        try:
            bot.reply_to(message, "❌ Ответьте на сообщение, которое нужно удалить")
        except:
            pass
        return

    try:
        chat_id = message.chat.id
        target_message_id = message.reply_to_message.message_id
        thread_id = None
        if hasattr(message, 'message_thread_id'):
            thread_id = message.message_thread_id

        log_action(message.from_user, "Удаление сообщения", 
                   f"ID сообщения: {target_message_id}, Чат: {chat_id}, Топик: {thread_id}")

        bot.delete_message(chat_id, target_message_id)

        try:
            bot.delete_message(chat_id, message.message_id)
        except:
            pass

        confirm_text = "✅ Сообщение удалено"
        try:
            if thread_id and chat_id != thread_id:
                confirm_msg = bot.send_message(chat_id, confirm_text, message_thread_id=thread_id)
            else:
                confirm_msg = bot.send_message(chat_id, confirm_text)

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
    log_action(message.from_user, "Команда /clear_all", "Начало выполнения")
    
    if not is_in_correct_topic(message):
        logger.warning(f"Попытка использования /clear_all вне топика {TOPIC_ID} от пользователя {get_user_info(message.from_user)}")
        error_text = f"❌ Команда /clear_all доступна только в топике {TOPIC_ID}"
        bot.send_message(message.chat.id, error_text)
        return

    if not is_admin(message.from_user.id):
        logger.warning(f"Пользователь {get_user_info(message.from_user)} попытался использовать /clear_all без прав")
        bot.send_message(message.chat.id, "❌ У вас нет прав для удаления сообщений")
        return

    try:
        confirm_text = "⚠️ <b>ВНИМАНИЕ!</b>\n\n"
        confirm_text += "Вы собираетесь удалить ВСЕ сообщения в этом топике.\n"
        confirm_text += "Это действие НЕОБРАТИМО!\n\n"
        confirm_text += "Для подтверждения отправьте: <code>/confirm_clear_all</code>\n"
        confirm_text += "Для отмены отправьте: <code>/cancel</code>"

        user_data[message.from_user.id] = {
            'waiting_confirm': 'clear_all',
            'chat_id': message.chat.id
        }

        log_action(message.from_user, "Запрос подтверждения /clear_all")
        bot.send_message(message.chat.id, confirm_text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка в /clear_all: {e}")

@bot.message_handler(commands=['confirm_clear_all'])
def confirm_clear_all_command(message):
    log_action(message.from_user, "Команда /confirm_clear_all", "Начало выполнения")
    
    if not is_in_correct_topic(message):
        return

    user_id = message.from_user.id
    if not is_admin(user_id) or user_id not in user_data or user_data[user_id].get('waiting_confirm') != 'clear_all':
        return

    try:
        chat_id = user_data[user_id].get('chat_id')
        del user_data[user_id]

        user_info = get_user_info(message.from_user)
        logger.warning(f"Админ {user_info} начал удаление ВСЕХ сообщений в чате {chat_id}")

        warning_msg = bot.send_message(chat_id, "⚠️ Начинаю удаление ВСЕХ сообщений... Это может занять время.")

        deleted_total = 0
        max_messages = 1000

        for msg_id in range(1, max_messages + 1):
            try:
                if msg_id == warning_msg.message_id:
                    continue
                bot.delete_message(chat_id, msg_id)
                deleted_total += 1
                if deleted_total % 10 == 0:
                    threading.Event().wait(0.1)
            except:
                continue

        final_text = f"✅ Удалено {deleted_total} сообщений."
        bot.edit_message_text(final_text, chat_id=chat_id, message_id=warning_msg.message_id)

        threading.Timer(10.0, lambda: bot.delete_message(chat_id, warning_msg.message_id)).start()
        log_action(message.from_user, "Завершение /clear_all", f"Удалено сообщений: {deleted_total}")
    except Exception as e:
        logger.error(f"Ошибка в /confirm_clear_all: {e}")
        log_action(message.from_user, "Ошибка в /confirm_clear_all", f"Ошибка: {str(e)}")

@bot.message_handler(commands=['call_all'])
def call_all_members_command(message):
    log_action(message.from_user, "Команда /call_all", "Начало выполнения")

    if message.chat.type not in ['group', 'supergroup']:
        bot.send_message(message.chat.id, "❌ Эта команда работает только в групповых чатах")
        log_action(message.from_user, "Попытка использования /call_all не в групповом чате")
        return

    if not is_admin(message.from_user.id):
        logger.warning(f"Пользователь {get_user_info(message.from_user)} попытался использовать /call_all без прав")
        bot.send_message(message.chat.id, "❌ У вас нет прав для упоминания всех участников")
        return

    try:
        text = ""
        if len(message.text.split(' ', 1)) > 1:
            args = message.text.split(' ', 1)[1]
            text = args.strip('"\'')

        if not text:
            text = "🔔 Внимание всем участникам чата!"

        chat_id = message.chat.id

        try:
            mention_message = bot.send_message(chat_id,
                                               "​@all",
                                               parse_mode='HTML',
                                               message_thread_id=2)

            main_message = bot.send_message(chat_id,
                                            f"{text}\n\n<i>Сообщение будет удалено через минуту</i>",
                                            parse_mode='HTML',
                                            message_thread_id=2)

            log_action(message.from_user, "Упоминание отправлено", f"Текст: {text}")

            try:
                bot.delete_message(chat_id, message.message_id)
            except:
                pass

            threading.Timer(2.0, lambda: delete_specific_message(chat_id, mention_message.message_id, 2)).start()
            threading.Timer(60.0, lambda: delete_specific_message(chat_id, main_message.message_id, 2)).start()

            if hasattr(message, 'message_thread_id') and message.message_thread_id:
                bot.send_message(chat_id,
                                 "✅ Упоминание отправлено в топик 2",
                                 message_thread_id=message.message_thread_id)

        except Exception as e:
            logger.error(f"Ошибка отправки упоминания: {e}")
            try:
                mention_message = bot.send_message(chat_id, "​@all", parse_mode='HTML')
                main_message = bot.send_message(chat_id,
                                                f"{text}\n\n<i>Сообщение будет удалено через минуту</i>",
                                                parse_mode='HTML')
                try:
                    bot.delete_message(chat_id, message.message_id)
                except:
                    pass
                threading.Timer(2.0, lambda: delete_specific_message(chat_id, mention_message.message_id)).start()
                threading.Timer(60.0, lambda: delete_specific_message(chat_id, main_message.message_id)).start()
            except Exception as e2:
                logger.error(f"Ошибка при альтернативной отправке: {e2}")
                bot.send_message(chat_id, f"❌ Ошибка при отправке упоминания: {str(e2)}")
    except Exception as e:
        logger.error(f"Ошибка в /call_all: {e}")
        try:
            bot.send_message(message.chat.id, f"❌ Ошибка при выполнении команды: {str(e)}")
        except:
            pass

def delete_specific_message(chat_id, message_id, thread_id=None):
    try:
        if thread_id:
            bot.delete_message(chat_id, message_id)
        else:
            bot.delete_message(chat_id, message_id)
        logger.info(f"Сообщение удалено: chat_id={chat_id}, message_id={message_id}")
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщения: {e}")

@bot.message_handler(commands=['admin_help'])
def admin_help_command(message):
    user_id = message.from_user.id
    help_text = "🛠️ <b>Команды администратора:</b>\n\n"

    if is_admin(user_id):
        help_text += "<b>Общие команды:</b>\n"
        help_text += "<code>/del_mes</code> - удалить сообщение (ответьте на него) - работает везде\n"
        help_text += f"<code>/clear_all</code> - удалить все сообщения в топике (только в топике {TOPIC_ID})\n"
        help_text += "<code>/call_all</code> - упомянуть всех участников чата (кратковременное сообщение)\n"
        help_text += "<code>/set_birthday_time час</code> - установить время отправки поздравлений\n"
        help_text += "<code>/check_birthdays</code> - проверить и отправить поздравления\n\n"
        
        help_text += "<b>Для зачетов:</b>\n"
        help_text += "<code>/add_exam</code> - добавить зачёт (с файлами для подготовки)\n"
        help_text += "<code>/delete_exam</code> - удалить зачёт\n"
        help_text += "<code>/done_exam</code> - завершить добавление файлов к зачету\n"
        help_text += "<code>/skip_exam</code> - пропустить добавление файлов к зачету\n\n"
        
        help_text += "<b>Для справочных материалов:</b>\n"
        help_text += "<code>/done_reference</code> - завершить добавление файлов в папку\n"
        help_text += "<code>/done_request</code> - завершить создание запроса на добавление\n"
        help_text += "Управление через меню: создание папок, добавление файлов, обработка запросов\n\n"
        
        help_text += "<b>Для управления запросами:</b>\n"
        help_text += "1. Используйте меню 'Запросы на добавление' для просмотра ожидающих запросов\n"
        help_text += "2. Просмотрите детали запроса и файлы\n"
        help_text += "3. Одобрите или отклоните запрос\n"
        help_text += "4. При одобрении файлы автоматически добавляются в выбранную папку\n"
    else:
        help_text += "❌ <b>У вас нет прав администратора</b>\n\n"

    help_text += "<b>Общие команды:</b>\n"
    help_text += "<code>/help</code> - общая справка по боту\n"
    help_text += "<code>/admin_help</code> - эта справка\n"

    bot.send_message(message.chat.id, help_text, parse_mode='HTML',
                     reply_markup=create_back_to_menu_button())

# Универсальная функция отмены
def cancel_operation(message):
    user_id = message.from_user.id
    if user_id in user_data:
        step = user_data[user_id].get('step', '')
        
        # Если это создание запроса
        if step in ['select_folder_for_request', 'request_description', 'waiting_request_files']:
            cancel_request_operation(message)
            return
        
        # Если это добавление справочных файлов
        if step == 'waiting_reference_files':
            if 'reference_temp_files' in user_data[user_id]:
                for file_name in user_data[user_id]['reference_temp_files']:
                    try:
                        file_path = os.path.join(REFERENCE_FILES_DIR, file_name)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception as e:
                        logger.error(f"Ошибка при удалении временного файла справочных материалов: {e}")
            log_action(message.from_user, "Отмена добавления справочных файлов")
        
        # Если это создание папки
        elif step in ['reference_folder_name', 'reference_folder_subject', 'reference_folder_description']:
            log_action(message.from_user, "Отмена создания папки")
        
        # Если это запрос диапазона файлов
        elif step == 'waiting_files_range':
            log_action(message.from_user, "Отмена запроса файлов")
        
        # Если это добавление зачета
        elif step in ['exam_subject_name', 'exam_description', 'exam_date', 
                      'exam_file_choice', 'waiting_exam_file']:
            cancel_exam_operation(message)
            return
        
        # Если это добавление решения
        elif step == 'waiting_solution_file':
            log_action(message.from_user, "Отмена добавления решения")
        else:
            log_action(message.from_user, "Отмена операции")
        
        # Удаляем временные файлы для ДЗ
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

# Основной цикл
if __name__ == '__main__':
    init_db()
    logger.info("Бот запущен!")
    logger.info(f"Администраторы: {ADMIN_IDS}")
    logger.info("Ожидание команд...")

    # Запускаем планировщик уведомлений
    notification_thread = threading.Thread(target=notification_scheduler, daemon=True)
    notification_thread.start()
    logger.info("Планировщик уведомлений запущен")

    # Логируем команды администратора
    logger.info("Команды администратора активированы:")
    logger.info("/del_mes - удалить сообщение (ответьте на него) - работает везде")
    logger.info(f"/clear_all - удалить все сообщения в топике (только в топике {TOPIC_ID})")
    logger.info("/call_all - упомянуть всех участников чата (кратковременное сообщение)")
    logger.info("/admin_help - справка по командам администратора")

    try:
        bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")