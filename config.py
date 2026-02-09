# config.py
import os

# Базовые пути
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILES_DIR = os.path.join(BASE_DIR, 'homework_files')
EXAM_FILES_DIR = os.path.join(BASE_DIR, 'exam_files')
REFERENCE_FILES_DIR = os.path.join(BASE_DIR, 'reference_files')
BIRTHDAYS_FILE = os.path.join(BASE_DIR, 'birthdays.txt')

# Константы бота
TOKEN = '8549158268:AAHmfHcRnUpTxilyY72RL8pWK9Fr7qTcKBU'
TOPIC_ID = 60817
CONSOLE_CHAT_ID = -1002530863470
NOTIFICATION_CHAT_ID = 2
BIRTHDAY_WISH_TIME = 9