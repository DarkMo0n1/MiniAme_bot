# file_handlers.py
import os
import sqlite3
import logging
from datetime import datetime, timedelta
from telebot import types

# Импорт из config и bot_instance
from config import FILES_DIR, EXAM_FILES_DIR, REFERENCE_FILES_DIR, TOPIC_ID
from bot_instance import bot
from keyboards import create_back_to_menu_button
from auth import is_admin
import uuid

logger = logging.getLogger(__name__)

# Импорт из main
from main import user_data, log_action, get_user_info

# ===== ОБЩИЕ ФУНКЦИИ =====

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
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, 'wb') as f:
            f.write(file_content)

        logger.info(f"Файл сохранен: {file_path}")
        return unique_filename
    except Exception as e:
        logger.error(f"Ошибка при сохранении файла: {e}")
        return None


def save_exam_file_locally(file_content, original_name, file_type):
    try:
        unique_filename = generate_unique_filename(original_name, file_type)
        file_path = os.path.join(EXAM_FILES_DIR, unique_filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, 'wb') as f:
            f.write(file_content)

        logger.info(f"Файл зачета сохранен: {file_path}")
        return unique_filename
    except Exception as e:
        logger.error(f"Ошибка при сохранении файла зачета: {e}")
        return None


# ===== ОБРАБОТЧИКИ ФАЙЛОВ =====

@bot.message_handler(content_types=['photo', 'document', 'audio', 'video', 'voice'])
def handle_file(message):
    from main import check_topic_access

    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    file_types = {
        'photo': ('фото', 'Фото'),
        'document': ('документ', 'Документ'),
        'audio': ('аудио', 'Аудио'),
        'video': ('видео', 'Видео'),
        'voice': ('голосовое сообщение', 'Голосовое сообщение')
    }

    content_type = message.content_type
    if content_type not in file_types:
        return

    file_type, default_name = file_types[content_type]

    # Определяем тип операции
    if user_id in user_data:
        step = user_data[user_id].get('step', '')

        # Обработка файлов для домашних заданий
        if step == 'waiting_file':
            process_homework_file(message, user_id, content_type, file_type, default_name)

        # Обработка файлов для решений
        elif step == 'waiting_solution_file':
            process_solution_file(message, user_id, content_type, file_type, default_name)

        # Обработка файлов для зачетов
        elif step == 'waiting_exam_file':
            process_exam_file(message, user_id, content_type, file_type, default_name)

        # Обработка справочных файлов
        elif step == 'waiting_reference_files':
            from reference_system import process_reference_file
            process_reference_file(message, user_id, content_type, file_type, default_name)

        # Обработка файлов запросов
        elif step == 'waiting_request_files':
            from request_system import process_request_file
            process_request_file(message, user_id, content_type, file_type, default_name)


def process_homework_file(message, user_id, content_type, file_type, default_name):
    """Обрабатывает файл для домашнего задания"""
    try:
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


def process_solution_file(message, user_id, content_type, file_type, default_name):
    """Обрабатывает файл решения для домашнего задания"""
    try:
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
            text = f"✅ Файл сохранен как решение: {original_name}\n📁 Тип: {file_type}\n📊 Всего решений: {files_count}\n\nОтправьте ещё файл или /done для завершения."

            log_action(message.from_user, "Добавление файла решения", f"Тип: {file_type}, Имя: {original_name}")

            if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
                bot.send_message(message.chat.id, text, message_thread_id=TOPIC_ID)
            else:
                bot.send_message(message.chat.id, text)
        else:
            send_error(message, "❌ Не удалось сохранить файл. Попробуйте еще раз.")

    except Exception as e:
        logger.error(f"Ошибка при обработке файла решения: {e}")
        send_error(message, "❌ Не удалось загрузить файл. Попробуйте другой файл.")


def process_exam_file(message, user_id, content_type, file_type, default_name):
    """Обрабатывает файл для зачета"""
    try:
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

        downloaded_file = bot.download_file(file_info.file_path)
        file_name = save_exam_file_locally(downloaded_file, original_name, file_type)

        if file_name:
            user_data[user_id]['exam_files'].append({
                'file_name': file_name,
                'file_type': file_type,
                'original_name': original_name
            })
            user_data[user_id]['exam_temp_files'].append(file_name)

            files_count = len(user_data[user_id]['exam_files'])
            text = f"✅ Файл сохранен: {original_name}\n📁 Тип: {file_type}\n📊 Всего файлов: {files_count}\n\nОтправьте ещё файл или /done_exam для завершения."

            log_action(message.from_user, "Добавление файла к зачету",
                       f"Тип: {file_type}, Имя: {original_name}")

            if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
                bot.send_message(message.chat.id, text, message_thread_id=TOPIC_ID)
            else:
                bot.send_message(message.chat.id, text)
        else:
            send_error(message, "❌ Не удалось сохранить файл. Попробуйте еще раз.")

    except Exception as e:
        logger.error(f"Ошибка при обработке файла зачета: {e}")
        send_error(message, "❌ Не удалось загрузить файл. Попробуйте другой файл или отправьте /skip_exam.")


def send_error(message, text):
    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, text, message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, text)


# ===== КОМАНДЫ ДЛЯ ЗАВЕРШЕНИЯ ДОБАВЛЕНИЯ ФАЙЛОВ =====

@bot.message_handler(commands=['done'])
def finish_adding_files(message):
    from main import check_topic_access
    from handlers import save_homework_to_db

    if not check_topic_access(message):
        return

    user_id = message.from_user.id

    # Завершение добавления файлов к домашнему заданию
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

    # Завершение добавления файлов решения
    elif user_id in user_data and user_data[user_id].get('step') == 'waiting_solution_file':
        files_count = save_solution_to_db(user_id)

        if files_count > 0:
            subject_name = user_data[user_id].get('subject_name', '')
            response = f"✅ <b>Решение успешно добавлено!</b>\n\n"
            response += f"📚 <b>К заданию:</b> {subject_name}\n"
            response += f"📎 <b>Добавлено файлов:</b> {files_count}\n"
            response += f"👤 <b>Добавил:</b> {user_data[user_id].get('added_by', 'Аноним')}"

            log_action(message.from_user, "Завершение добавления решения",
                       f"Файлов: {files_count}, Предмет: {subject_name}")
        elif files_count == 0:
            response = "❌ <b>Не добавлено ни одного файла!</b>\n"
            response += "Для добавления решения отправьте файл."
            log_action(message.from_user, "Попытка сохранения решения без файлов")
        else:
            response = "❌ <b>Ошибка при сохранении решения!</b>"
            log_action(message.from_user, "Ошибка сохранения решения")

        if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
            bot.send_message(message.chat.id, response + "\n\n🏠 Вы можете вернуться в главное меню:",
                             parse_mode='HTML', reply_markup=create_back_to_menu_button(),
                             message_thread_id=TOPIC_ID)
        else:
            bot.send_message(message.chat.id, response + "\n\n🏠 Вы можете вернуться в главное меню:",
                             parse_mode='HTML', reply_markup=create_back_to_menu_button())

        if user_id in user_data:
            del user_data[user_id]


@bot.message_handler(commands=['skip'])
def skip_adding_files(message):
    from main import check_topic_access
    from handlers import save_homework_to_db

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


# ===== ФУНКЦИИ ДЛЯ СОХРАНЕНИЯ РЕШЕНИЙ =====

def save_solution_to_db(user_id):
    """Сохраняет решение к заданию в базу данных"""
    if user_id not in user_data:
        return -1

    conn = None
    try:
        conn = sqlite3.connect('homework.db')
        cursor = conn.cursor()

        homework_id = user_data[user_id].get('homework_id')
        added_by = user_data[user_id].get('added_by', 'Аноним')

        files_count = 0
        for file_data in user_data[user_id].get('files', []):
            cursor.execute('''
                           INSERT INTO homework_solutions (homework_id, file_name, file_type, original_name, added_by)
                           VALUES (?, ?, ?, ?, ?)
                           ''', (
                               homework_id,
                               file_data.get('file_name'),
                               file_data['file_type'],
                               file_data.get('original_name', ''),
                               added_by
                           ))
            files_count += 1

        conn.commit()
        logger.info(f"Решение сохранено в БД: ID задания={homework_id}, файлов={files_count}")

        return files_count

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass

        # Удаляем временные файлы при ошибке
        for file_name in user_data[user_id].get('temp_files', []):
            try:
                file_path = os.path.join(FILES_DIR, file_name)
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass

        logger.error(f"Ошибка сохранения решения в БД: {e}")
        return -1
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


# ===== ФУНКЦИИ ДЛЯ ЗАЧЕТОВ =====

def add_exam_command_handler(message):
    """Начинает процесс добавления зачета с возможностью прикрепления файлов"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
            bot.send_message(message.chat.id, "❌ У вас нет прав для добавления зачетов",
                             message_thread_id=TOPIC_ID)
        else:
            bot.send_message(message.chat.id, "❌ У вас нет прав для добавления зачетов")
        return

    if user_id in user_data:
        # Очищаем временные файлы, если есть
        if 'exam_temp_files' in user_data[user_id]:
            for file_name in user_data[user_id]['exam_temp_files']:
                try:
                    file_path = os.path.join(EXAM_FILES_DIR, file_name)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except:
                    pass
        del user_data[user_id]

    user_data[user_id] = {
        'step': 'exam_subject_name',
        'exam_files': [],
        'exam_temp_files': [],
        'added_by': f"{message.from_user.first_name or 'Аноним'}",
        'chat_id': message.chat.id,
        'topic_id': message.message_thread_id if hasattr(message, 'message_thread_id') else None
    }

    log_action(message.from_user, "Начало добавления зачета с файлами")

    text = "📝 <b>Добавление зачета</b>\n\n1. Введите название предмета:\n<i>Пример: Математика, Физика</i>\n\n<i>Или отправьте /cancel для отмены</i>"

    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, text, parse_mode='HTML',
                         reply_markup=create_back_to_menu_button(), message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, text, parse_mode='HTML',
                         reply_markup=create_back_to_menu_button())


@bot.message_handler(commands=['done_exam'])
def finish_adding_exam_files(message):
    """Завершает добавление файлов к зачету и сохраняет зачет"""
    from main import check_topic_access

    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if user_id in user_data and user_data[user_id].get('step') == 'waiting_exam_file':
        if all(key in user_data[user_id] for key in ['subject_name', 'description', 'exam_date']):
            files_count = save_exam_with_files_to_db(user_id)

            if files_count > 0:
                response = f"✅ <b>Зачет успешно добавлен!</b>\nПрикреплено файлов: {files_count}"
                log_action(message.from_user, "Завершение добавления зачета с файлами",
                           f"Файлов: {files_count}")
            elif files_count == 0:
                response = "✅ <b>Зачет успешно добавлен без файлов!</b>"
                log_action(message.from_user, "Завершение добавления зачета без файлов", "Успешно")
            else:
                response = "❌ <b>Ошибка при добавлении зачета!</b>"
                log_action(message.from_user, "Завершение добавления зачета", "Ошибка сохранения")

            if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
                bot.send_message(message.chat.id, response + "\n\n🏠 Вы можете вернуться в главное меню:",
                                 parse_mode='HTML', reply_markup=create_back_to_menu_button(),
                                 message_thread_id=TOPIC_ID)
            else:
                bot.send_message(message.chat.id, response + "\n\n🏠 Вы можете вернуться в главное меню:",
                                 parse_mode='HTML', reply_markup=create_back_to_menu_button())

            # Очищаем временные файлы
            if user_id in user_data and 'exam_temp_files' in user_data[user_id]:
                user_data[user_id]['exam_temp_files'] = []

            if user_id in user_data:
                del user_data[user_id]
        else:
            send_error(message, "❌ Не все данные заполнены. Начните сначала с добавления зачета")


@bot.message_handler(commands=['skip_exam'])
def skip_adding_exam_files(message):
    """Пропускает добавление файлов к зачету"""
    from main import check_topic_access

    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if user_id in user_data and user_data[user_id].get('step') == 'waiting_exam_file':
        if all(key in user_data[user_id] for key in ['subject_name', 'description', 'exam_date']):
            save_exam_to_db(user_id)
            text = "✅ <b>Зачет успешно добавлен без файлов!</b>\n\n🏠 Вы можете вернуться в главное меню:"

            log_action(message.from_user, "Пропуск добавления файлов к зачету", "Сохранено без файлов")

            if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
                bot.send_message(message.chat.id, text, parse_mode='HTML',
                                 reply_markup=create_back_to_menu_button(), message_thread_id=TOPIC_ID)
            else:
                bot.send_message(message.chat.id, text, parse_mode='HTML',
                                 reply_markup=create_back_to_menu_button())

            # Очищаем временные файлы
            if user_id in user_data and 'exam_temp_files' in user_data[user_id]:
                user_data[user_id]['exam_temp_files'] = []

            if user_id in user_data:
                del user_data[user_id]
        else:
            send_error(message, "❌ Не все данные заполнены. Начните сначала с добавления зачета")


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


def save_exam_with_files_to_db(user_id):
    """Сохраняет зачет с прикрепленными файлами"""
    if user_id not in user_data:
        return -1

    conn = None
    try:
        conn = sqlite3.connect('homework.db')
        cursor = conn.cursor()

        # Сохраняем зачет
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

        exam_id = cursor.lastrowid

        # Сохраняем файлы
        files_count = 0
        for file_data in user_data[user_id].get('exam_files', []):
            cursor.execute('''
                           INSERT INTO exam_files (exam_id, file_name, file_type, original_name, added_by)
                           VALUES (?, ?, ?, ?, ?)
                           ''', (
                               exam_id,
                               file_data.get('file_name'),
                               file_data['file_type'],
                               file_data.get('original_name', ''),
                               user_data[user_id].get('added_by', 'Аноним')
                           ))
            files_count += 1

        conn.commit()
        logger.info(f"Зачет сохранен в БД с {files_count} файлами: ID={exam_id}")

        return files_count

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass

        # Удаляем временные файлы при ошибке
        for file_name in user_data[user_id].get('exam_temp_files', []):
            try:
                file_path = os.path.join(EXAM_FILES_DIR, file_name)
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass

        logger.error(f"Ошибка сохранения зачета с файлами в БД: {e}")
        return -1
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def cancel_exam_operation(message):
    """Отменяет операцию добавления зачета"""
    user_id = message.from_user.id
    if user_id in user_data:
        # Удаляем временные файлы
        if 'exam_temp_files' in user_data[user_id]:
            for file_name in user_data[user_id]['exam_temp_files']:
                try:
                    file_path = os.path.join(EXAM_FILES_DIR, file_name)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    logger.error(f"Ошибка при удалении временного файла зачета: {e}")

        del user_data[user_id]

    log_action(message.from_user, "Отмена добавления зачета")

    markup = create_back_to_menu_button()
    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, "❌ Добавление зачета отменено.\n\n🏠 Вы можете вернуться в главное меню.",
                         reply_markup=markup, message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, "❌ Добавление зачета отменено.\n\n🏠 Вы можете вернуться в главное меню.",
                         reply_markup=markup)


def show_exam_files(call, exam_id):
    """Показывает файлы, прикрепленные к зачету"""
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    thread_id = None
    if call.message.chat.type in ['group', 'supergroup'] and hasattr(call.message, 'message_thread_id'):
        thread_id = call.message.message_thread_id

    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()

    cursor.execute('SELECT subject_name, exam_date, description, added_by FROM exams WHERE id = ?', (exam_id,))
    exam_info = cursor.fetchone()

    if not exam_info:
        bot.answer_callback_query(call.id, "❌ Зачет не найден")
        return

    subject_name, exam_date, description, added_by = exam_info

    cursor.execute('SELECT file_name, file_type, original_name FROM exam_files WHERE exam_id = ?', (exam_id,))
    files = cursor.fetchall()
    conn.close()

    if not files:
        response = f"📁 <b>Файлы для подготовки к зачету:</b> {subject_name}\n"
        response += f"📅 <b>Дата:</b> {datetime.strptime(exam_date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
        response += f"👤 <b>Добавил:</b> {added_by}\n"
        if description:
            response += f"📝 <b>Описание:</b> {description}\n"
        response += f"\n📭 К этому зачету нет прикрепленных файлов для подготовки.\n"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Назад к зачетам", callback_data="view_exams_menu"))
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

    response = f"📁 <b>Файлы для подготовки к зачету:</b> {subject_name}\n"
    response += f"📅 <b>Дата:</b> {datetime.strptime(exam_date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
    response += f"👤 <b>Добавил:</b> {added_by}\n"
    if description:
        response += f"📝 <b>Описание:</b> {description}\n"
    response += f"\n<b>Найдено файлов:</b> {len(files)}\n"
    response += f"📤 <b>Отправляю файлы...</b>"

    bot.answer_callback_query(call.id, f"📁 Отправляю {len(files)} файл(ов)...")

    bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=response,
        parse_mode='HTML'
    )

    for file_name, file_type, original_name in files:
        file_path = os.path.join(EXAM_FILES_DIR, file_name)

        if not os.path.exists(file_path):
            logger.error(f"Файл зачета не найден: {file_path}")
            continue

        try:
            caption = f"📚 Зачет: {subject_name}"
            if original_name:
                caption = f"📁 {original_name}\n{caption}"

            with open(file_path, 'rb') as file:
                if file_type == 'фото':
                    if thread_id:
                        bot.send_photo(chat_id, file, caption=caption, message_thread_id=thread_id)
                    else:
                        bot.send_photo(chat_id, file, caption=caption)
                elif file_type == 'документ':
                    if thread_id:
                        bot.send_document(chat_id, file, caption=caption, message_thread_id=thread_id)
                    else:
                        bot.send_document(chat_id, file, caption=caption)
                elif file_type == 'аудио':
                    if thread_id:
                        bot.send_audio(chat_id, file, caption=caption, message_thread_id=thread_id)
                    else:
                        bot.send_audio(chat_id, file, caption=caption)
                elif file_type == 'видео':
                    if thread_id:
                        bot.send_video(chat_id, file, caption=caption, message_thread_id=thread_id)
                    else:
                        bot.send_video(chat_id, file, caption=caption)
                elif file_type == 'голосовое сообщение':
                    if thread_id:
                        bot.send_voice(chat_id, file, caption=caption, message_thread_id=thread_id)
                    else:
                        bot.send_voice(chat_id, file, caption=caption)
                else:
                    if thread_id:
                        bot.send_document(chat_id, file, caption=caption, message_thread_id=thread_id)
                    else:
                        bot.send_document(chat_id, file, caption=caption)

            logger.info(f"Файл зачета отправлен: {file_name}")

        except Exception as e:
            logger.error(f"Ошибка при отправке файла зачета {file_name}: {e}")
            error_msg = f"❌ Не удалось отправить файл: {original_name or file_name}"
            if thread_id:
                bot.send_message(chat_id, error_msg, message_thread_id=thread_id)
            else:
                bot.send_message(chat_id, error_msg)

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад к зачетам", callback_data="view_exams_menu"))
    markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))

    final_msg = f"✅ Все файлы отправлены!\n\n📚 <b>Зачет:</b> {subject_name}\n📁 <b>Файлов для подготовки:</b> {len(files)}"
    if thread_id:
        bot.send_message(chat_id, final_msg, parse_mode='HTML',
                         reply_markup=markup, message_thread_id=thread_id)
    else:
        bot.send_message(chat_id, final_msg, parse_mode='HTML', reply_markup=markup)


def show_exam_dates_list(call):
    """Показывает список дат с зачетами"""
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


# Добавьте недостающие функции, которые используются в коде
def show_exams_for_date(call, date_str, user_id):
    """Показывает зачеты на указанную дату"""
    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, subject_name, description, added_by FROM exams WHERE exam_date = ? ORDER BY subject_name',
        (date_str,))
    exams = cursor.fetchall()
    conn.close()

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%d.%m.%Y')
    except:
        formatted_date = date_str

    if not exams:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"📭 На {formatted_date} зачетов нет.",
            reply_markup=create_back_to_menu_button()
        )
        return

    response = f"📅 <b>Зачеты на {formatted_date}:</b>\n\n"

    markup = types.InlineKeyboardMarkup(row_width=2)

    for exam in exams:
        exam_id, subject_name, description, added_by = exam
        short_name = subject_name[:15] + "..." if len(subject_name) > 15 else subject_name

        response += f"📚 <b>{subject_name}</b>\n"
        response += f"   👤 Добавил: {added_by}\n"
        if description:
            response += f"   📝 {description}\n"
        response += "\n"

        row_buttons = []
        row_buttons.append(types.InlineKeyboardButton(f"📁 {short_name}", callback_data=f"view_exam_files_{exam_id}"))

        if is_admin(user_id):
            row_buttons.append(types.InlineKeyboardButton(f"❌ {short_name}", callback_data=f"delete_exam_{exam_id}"))

        if row_buttons:
            markup.row(*row_buttons)

    markup.row(types.InlineKeyboardButton("🔙 К списку дат", callback_data="view_exams_menu"))
    markup.row(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=response,
        parse_mode='HTML',
        reply_markup=markup
    )


def show_exams_for_deletion(call):
    """Показывает список зачетов для удаления"""
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
            reply_markup=create_back_to_menu_button()
        )
        return

    response = "🗑️ <b>Выберите зачет для удаления:</b>\n\n"

    markup = types.InlineKeyboardMarkup(row_width=2)

    for exam in exams:
        exam_id, subject_name, exam_date = exam
        try:
            formatted_date = datetime.strptime(exam_date, '%Y-%m-%d').strftime('%d.%m.%Y')
        except:
            formatted_date = exam_date

        short_name = subject_name[:15] + "..." if len(subject_name) > 15 else subject_name
        button_text = f"{short_name} ({formatted_date})"

        markup.add(types.InlineKeyboardButton(button_text, callback_data=f"delete_exam_{exam_id}"))

    markup.row(types.InlineKeyboardButton("🔙 Назад", callback_data="exams_menu"))
    markup.row(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=response,
        parse_mode='HTML',
        reply_markup=markup
    )


def delete_exam_callback(call, exam_id):
    """Обрабатывает удаление зачета"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    if not is_admin(user_id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав для удаления зачетов")
        return

    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT subject_name, exam_date FROM exams WHERE id = ?', (exam_id,))
        exam_info = cursor.fetchone()

        if not exam_info:
            bot.answer_callback_query(call.id, "❌ Зачет не найден")
            conn.close()
            return

        subject_name, exam_date = exam_info
        cursor.execute('SELECT file_name FROM exam_files WHERE exam_id = ?', (exam_id,))
        files_to_delete = cursor.fetchall()

        for (file_name,) in files_to_delete:
            try:
                file_path = os.path.join(EXAM_FILES_DIR, file_name)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Файл зачета удален: {file_path}")
            except Exception as e:
                logger.error(f"Ошибка при удалении файла зачета {file_path}: {e}")
                pass

        cursor.execute('DELETE FROM exams WHERE id = ?', (exam_id,))
        conn.commit()
        conn.close()

        bot.answer_callback_query(call.id, f"✅ Зачет '{subject_name}' удален")
        log_action(call.from_user, "Удаление зачета", f"ID: {exam_id}, Предмет: {subject_name}")

        show_exam_dates_list(call)

    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        try:
            conn.close()
        except:
            pass
        logger.error(f"Ошибка при удалении зачета: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка при удалении зачета")


def show_upcoming_exams(call):
    """Показывает ближайшие зачеты"""
    today = datetime.now().date()
    next_month = today + timedelta(days=30)

    conn = sqlite3.connect('homework.db')
    cursor = conn.cursor()
    cursor.execute('''
                   SELECT id, subject_name, exam_date, description, added_by
                   FROM exams
                   WHERE exam_date >= ?
                     AND exam_date <= ?
                   ORDER BY exam_date
                   ''', (today.strftime('%Y-%m-%d'), next_month.strftime('%Y-%m-%d')))
    exams = cursor.fetchall()
    conn.close()

    if not exams:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="📭 Ближайших зачетов (в течение месяца) нет.",
            reply_markup=create_back_to_menu_button()
        )
        return

    response = "📅 <b>Ближайшие зачеты (в течение месяца):</b>\n\n"

    for exam in exams:
        exam_id, subject_name, exam_date, description, added_by = exam
        try:
            date_obj = datetime.strptime(exam_date, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d.%m.%Y')
            days_left = (date_obj.date() - today).days
        except:
            formatted_date = exam_date
            days_left = 0

        response += f"📚 <b>{subject_name}</b>\n"
        response += f"   📅 {formatted_date} (через {days_left} дней)\n"
        response += f"   👤 Добавил: {added_by}\n"
        if description:
            response += f"   📝 {description}\n"
        response += "\n"

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