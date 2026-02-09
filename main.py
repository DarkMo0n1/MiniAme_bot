# main.py
import sqlite3
import os
import threading
import logging
import pytz
from datetime import datetime
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

# Импорты из config
from config import *
from auth import ADMIN_IDS, is_admin

# Импорт экземпляра бота
from bot_instance import bot

# Глобальные переменные
user_data = {}
exam_notifications = {}
MOSCOW_TZ = timezone('Europe/Moscow')


# Функции для логирования (переместим сюда)
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


# Основные команды (оставьте здесь только самые базовые)
@bot.message_handler(commands=['start'])
def send_welcome(message):
    from keyboards import create_main_menu
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


# Универсальная функция отмены
def cancel_operation(message):
    from keyboards import create_back_to_menu_button
    user_id = message.from_user.id
    if user_id in user_data:
        # ... остальная логика cancel_operation ...
        pass

    markup = create_back_to_menu_button()
    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, "❌ Операция отменена.\n\n🏠 Вы можете вернуться в главное меню.",
                         reply_markup=markup, message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, "❌ Операция отменена.\n\n🏠 Вы можете вернуться в главное меню.",
                         reply_markup=markup)


# Основной цикл
if __name__ == '__main__':
    from database import init_db

    init_db()
    logger.info("Бот запущен!")
    logger.info(f"Администраторы: {ADMIN_IDS}")

    # Импортируем обработчики здесь, чтобы избежать циклических импортов
    import handlers
    import file_handlers

    logger.info("Ожидание команд...")

    try:
        bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")