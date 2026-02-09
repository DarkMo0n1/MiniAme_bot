import time
import threading
import logging
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)

def notification_scheduler():
    """Планировщик уведомлений"""
    while True:
        try:
            # Здесь будет логика уведомлений
            time.sleep(60)  # Проверка каждую минуту
        except Exception as e:
            logger.error(f"Ошибка в планировщике уведомлений: {e}")
            time.sleep(60)