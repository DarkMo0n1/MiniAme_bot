import time
import threading
import logging
from datetime import datetime
import pytz
from database import get_birthdays_by_month, get_month_name
from bot_instance import bot
from config import CONSOLE_CHAT_ID, TOPIC_ID, BIRTHDAY_WISH_TIME

logger = logging.getLogger(__name__)

# Храним дату последней отправки, чтобы не дублировать
_last_birthday_check_date = None

def birthday_scheduler():
    """Поток, проверяющий каждый день в заданный час наличие именинников"""
    global _last_birthday_check_date
    moscow_tz = pytz.timezone('Europe/Moscow')
    while True:
        try:
            now = datetime.now(moscow_tz)
            # Проверяем, что наступил нужный час и сегодня ещё не отправляли
            if now.hour == BIRTHDAY_WISH_TIME and _last_birthday_check_date != now.date():
                check_and_send_birthdays(now)
                _last_birthday_check_date = now.date()
            time.sleep(60)  # проверка каждую минуту
        except Exception as e:
            logger.error(f"Ошибка в планировщике дней рождения: {e}")
            time.sleep(60)

def check_and_send_birthdays(now):
    """Проверяет, есть ли именинники сегодня, и отправляет поздравление"""
    month = now.month
    day = now.day

    # Получаем список именинников на этот день
    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM birthdays WHERE month = ? AND day = ?', (month, day))
    birthdays = cursor.fetchall()
    conn.close()

    if not birthdays:
        return

    month_name = get_month_name(month, 'genitive')
    names = [b[0] for b in birthdays]
    if len(names) == 1:
        text = f"🎉 Сегодня, {day} {month_name}, день рождения празднует:\n<b>{names[0]}</b> 🎂\n\nПоздравляем!"
    else:
        text = f"🎉 Сегодня, {day} {month_name}, день рождения празднуют:\n"
        for name in names:
            text += f"• <b>{name}</b>\n"
        text += "\nПоздравляем!"

    try:
        if CONSOLE_CHAT_ID:
            if TOPIC_ID is not None:
                bot.send_message(CONSOLE_CHAT_ID, text, parse_mode='HTML', message_thread_id=TOPIC_ID)
            else:
                bot.send_message(CONSOLE_CHAT_ID, text, parse_mode='HTML')
        else:
            logger.warning("CONSOLE_CHAT_ID не задан, поздравление не отправлено")
    except Exception as e:
        logger.error(f"Не удалось отправить поздравление: {e}")