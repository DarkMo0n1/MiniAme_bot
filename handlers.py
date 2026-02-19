# handlers.py
import sqlite3
import os
from datetime import datetime, timedelta
from telebot import types

# Импорт из config и bot_instance
from config import FILES_DIR, TOPIC_ID
from bot_instance import bot
from keyboards import *
from auth import is_admin
import logging

logger = logging.getLogger(__name__)

# Импорт функций из main
from main import (
    user_data,
    log_action,
    check_topic_access,
    cancel_operation,
    get_user_info
)

# Импорт функций из file_handlers
from file_handlers import (
    save_file_locally,
    generate_unique_filename,
    save_solution_to_db,
    add_exam_command_handler,
    show_exam_dates_list,
    show_exams_for_date,
    show_exams_for_deletion,
    delete_exam_callback,
    show_upcoming_exams,
    show_exam_files,
    finish_adding_exam_files,
    skip_adding_exam_files,
    cancel_exam_operation
)
# ===== ОБРАБОТЧИКИ CALLBACK =====

@bot.callback_query_handler(func=lambda call: True)
def handle_all_callbacks(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    logger.info(f"Обработка callback от пользователя {user_id}: {call.data}")

    # Проверка доступа к топику
    if TOPIC_ID is not None and chat_id == call.message.chat.id:
        if call.message.chat.type in ['group', 'supergroup']:
            if hasattr(call.message, 'message_thread_id') and call.message.message_thread_id != TOPIC_ID:
                bot.answer_callback_query(call.id, "❌ Эта команда доступна только в определенном топике")
                return

    # Обработка основных меню
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
            add_exam_command_handler(call)
        else:
            bot.answer_callback_query(call.id, "❌ У вас нет прав для добавления зачетов")

    elif call.data == 'delete_exam_menu':
        bot.answer_callback_query(call.id)
        if is_admin(user_id):
            show_exams_for_deletion(call)
        else:
            bot.answer_callback_query(call.id, "❌ У вас нет прав для удаления зачетов")

    elif call.data == 'view_exams_menu':
        bot.answer_callback_query(call.id)
        show_exam_dates_list(call)

    elif call.data == 'upcoming_exams_menu':
        bot.answer_callback_query(call.id)
        show_upcoming_exams(call)

    elif call.data.startswith('view_exam_date_'):
        date_str = call.data.replace('view_exam_date_', '')
        show_exams_for_date(call, date_str, user_id)

    elif call.data.startswith('delete_exam_'):
        exam_id = int(call.data.replace('delete_exam_', ''))
        if is_admin(user_id):
            delete_exam_callback(call, exam_id)
        else:
            bot.answer_callback_query(call.id, "❌ У вас нет прав для удаления зачетов")

    # Обработчики домашних заданий
    elif call.data == 'add_homework_menu':
        bot.answer_callback_query(call.id)
        add_homework_command(call.message, call.from_user)  # передаём объект пользователя

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

    # Обработчики учителей
    elif call.data == 'teacher_name_menu':
        bot.answer_callback_query(call.id)
        show_teachers_menu(call)

    elif call.data in ['Математика', 'Информатика', 'Физика', 'История', 'Биология', 'ОБЖ',
                       'Химия', 'Литература', 'Русский', 'Английский', 'Физра', 'ВВС', 'Общество']:
        bot.answer_callback_query(call.id)
        show_teacher_info(call)

    elif call.data == 'help_menu':
        bot.answer_callback_query(call.id)
        show_help_menu(call)

    # Обработчики справочных материалов
    elif call.data == 'reference_materials_menu':
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="📖 <b>Справочные материалы</b>\n\n👇 Выберите действие:",
            parse_mode='HTML',
            reply_markup=create_reference_materials_menu(call.from_user.id)
        )
    
    elif call.data == 'view_reference_folders':
        bot.answer_callback_query(call.id)
        from reference_system import show_reference_folders
        show_reference_folders(call)
    
    elif call.data == 'create_reference_folder':
        bot.answer_callback_query(call.id)
        if is_admin(call.from_user.id):
            from reference_system import start_create_reference_folder
            start_create_reference_folder(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ У вас нет прав для создания папок")
    
    elif call.data == 'add_reference_files':
        bot.answer_callback_query(call.id)
        if is_admin(call.from_user.id):
            from reference_system import show_folders_for_adding_files
            show_folders_for_adding_files(call)
        else:
            bot.answer_callback_query(call.id, "❌ У вас нет прав для добавления файлов")
    
    elif call.data == 'search_reference_materials':
        bot.answer_callback_query(call.id)
        from reference_system import search_reference_materials
        search_reference_materials(call)
    
    elif call.data.startswith('view_folder_'):
        folder_id = int(call.data.replace('view_folder_', ''))
        bot.answer_callback_query(call.id)
        from reference_system import show_folder_files
        show_folder_files(call, folder_id)
    
    elif call.data.startswith('select_folder_'):
        folder_id = int(call.data.replace('select_folder_', ''))
        bot.answer_callback_query(call.id)
        from reference_system import start_add_files_to_folder
        start_add_files_to_folder(call, folder_id)
    
    elif call.data.startswith('request_files_'):
        folder_id = int(call.data.replace('request_files_', ''))
        bot.answer_callback_query(call.id)
        from reference_system import request_files_range
        request_files_range(call, folder_id)
    
    elif call.data.startswith('send_files_'):
        data_parts = call.data.replace('send_files_', '').split('_')
        folder_id = int(data_parts[0])
        start_range = int(data_parts[1])
        end_range = int(data_parts[2])
        bot.answer_callback_query(call.id)
        from reference_system import send_selected_files
        send_selected_files(call, folder_id, start_range, end_range)
    
    elif call.data.startswith('delete_folder_'):
        folder_id = int(call.data.replace('delete_folder_', ''))
        if is_admin(call.from_user.id):
            bot.answer_callback_query(call.id)
            from reference_system import delete_reference_folder
            delete_reference_folder(call, folder_id)
        else:
            bot.answer_callback_query(call.id, "❌ У вас нет прав для удаления папок")
    
    # Обработчики запросов
    elif call.data == 'request_add_files':
        bot.answer_callback_query(call.id)
        from request_system import start_request_add_files
        start_request_add_files(call)
    
    elif call.data == 'view_pending_requests':
        bot.answer_callback_query(call.id)
        if is_admin(call.from_user.id):
            from request_system import show_pending_requests
            show_pending_requests(call)
        else:
            bot.answer_callback_query(call.id, "❌ У вас нет прав для просмотра запросов")
    
    elif call.data.startswith('request_select_folder_'):
        folder_id = int(call.data.replace('request_select_folder_', ''))
        bot.answer_callback_query(call.id)
        from request_system import handle_select_folder_for_request
        handle_select_folder_for_request(call)
    
    elif call.data.startswith('review_request_'):
        request_id = int(call.data.replace('review_request_', ''))
        bot.answer_callback_query(call.id)
        from request_system import show_request_details
        show_request_details(call, request_id)
    
    elif call.data.startswith('view_request_'):
        request_id = int(call.data.replace('view_request_', ''))
        bot.answer_callback_query(call.id)
        from request_system import show_request_details
        show_request_details(call, request_id)
    
    elif call.data.startswith('preview_request_'):
        request_id = int(call.data.replace('preview_request_', ''))
        bot.answer_callback_query(call.id)
        from request_system import preview_request_files
        preview_request_files(call, request_id)
    
    elif call.data.startswith('approve_request_'):
        request_id = int(call.data.replace('approve_request_', ''))
        bot.answer_callback_query(call.id)
        if is_admin(call.from_user.id):
            from request_system import approve_request
            approve_request(call, request_id)
        else:
            bot.answer_callback_query(call.id, "❌ У вас нет прав для одобрения запросов")
    
    elif call.data.startswith('reject_request_'):
        request_id = int(call.data.replace('reject_request_', ''))
        bot.answer_callback_query(call.id)
        if is_admin(call.from_user.id):
            from request_system import reject_request
            reject_request(call, request_id)
        else:
            bot.answer_callback_query(call.id, "❌ У вас нет прав для отклонения запросов")
    
    # Обработчики файлов зачетов
    elif call.data.startswith('view_exam_files_'):
        exam_id = int(call.data.replace('view_exam_files_', ''))
        bot.answer_callback_query(call.id)
        from file_handlers import show_exam_files
        show_exam_files(call, exam_id)
    
    elif call.data in ['attach_exam_file', 'save_exam_without_file', 'cancel_exam_add']:
        handle_exam_callback(call)

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

def handle_exam_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    if call.data == 'attach_exam_file':
        bot.answer_callback_query(call.id)
        user_data[user_id]['step'] = 'waiting_exam_file'
        text = "4. Отправьте файлы для подготовки к зачету (документ, фото, аудио, видео):\n<i>Можно отправить несколько файлов</i>\n<i>Для завершения отправьте /done_exam</i>\n<i>Или отправьте /skip_exam чтобы продолжить без файлов</i>"

        log_action(call.from_user, "Запрос файлов для зачета")

        if chat_id and TOPIC_ID is not None:
            bot.send_message(chat_id, text, parse_mode='HTML', message_thread_id=TOPIC_ID)
        else:
            bot.send_message(chat_id, text, parse_mode='HTML')

    elif call.data == 'save_exam_without_file':
        bot.answer_callback_query(call.id)
        from file_handlers import save_exam_to_db
        if save_exam_to_db(user_id):
            log_action(call.from_user, "Сохранение зачета без файлов", "Успешно")
            text = "✅ <b>Зачет успешно добавлен без файлов!</b>"
        else:
            log_action(call.from_user, "Сохранение зачета без файлов", "Ошибка")
            text = "❌ <b>Ошибка при добавлении зачета!</b>"
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text + "\n\n🏠 Вы можете вернуться в главное меню:",
            parse_mode='HTML',
            reply_markup=create_back_to_menu_button()
        )
        
        if user_id in user_data and 'exam_temp_files' in user_data[user_id]:
            user_data[user_id]['exam_temp_files'] = []
        
        if user_id in user_data:
            del user_data[user_id]

    elif call.data == 'cancel_exam_add':
        bot.answer_callback_query(call.id)
        from file_handlers import cancel_exam_operation
        cancel_exam_operation(call.message)

# ===== ФУНКЦИИ ДЛЯ ДОМАШНИХ ЗАДАНИЙ =====

@bot.message_handler(commands=['add_homework'])
def add_homework_command(message, user):
    if not check_topic_access(message):
        return

    user_id = user.id
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
        'temp_files': [],
        'added_by': f"{user.first_name or 'Аноним'}",
        'chat_id': message.chat.id,
        'topic_id': message.message_thread_id if hasattr(message, 'message_thread_id') else None
    }

    log_action(user, "Начало добавления домашнего задания")

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
        from main import cancel_operation
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
        from main import cancel_operation
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
    func=lambda message: message.from_user.id in user_data and
                         user_data[message.from_user.id].get('step') == 'file_choice')
def handle_file_choice_text(message):
    """Напоминает пользователю, что нужно выбрать действие кнопками"""
    user_id = message.from_user.id
    text = "⚠️ Пожалуйста, используйте кнопки ниже для выбора действия (прикрепить файл / сохранить без файла / отменить)."
    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, text, message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, text)


@bot.message_handler(
    func=lambda message: message.from_user.id in user_data and user_data.get(message.from_user.id, {}).get(
        'step') == 'date')
def process_date(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    if message.text.lower() == '/cancel':
        from main import cancel_operation
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

    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for hw in homework_list:
        hw_id, subject_name, _, _, file_count = hw
        short_name = subject_name[:15] + "..." if len(subject_name) > 15 else subject_name
        
        row_buttons = []
        
        if file_count > 0:
            row_buttons.append(types.InlineKeyboardButton(f"📁 {short_name}", callback_data=f"view_files_{hw_id}"))
        else:
            row_buttons.append(types.InlineKeyboardButton(f"📄 {short_name}", callback_data=f"view_files_{hw_id}"))
        
        row_buttons.append(types.InlineKeyboardButton(f"📝 {short_name}", callback_data=f"view_solutions_{hw_id}"))
        
        if is_admin(user_id):
            row_buttons.append(types.InlineKeyboardButton(f"❌ {short_name}", callback_data=f"delete_{hw_id}"))
        
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

    response = f"📁 <b>Файлы к заданию:</b> {subject_name}\n<b>👤 Добавил:</b> {added_by}\n"
    if homework_description:
        response += f"<b>Описание:</b> {homework_description}\n"
    response += f"\n<b>Отправляю {len(files)} файл(ов)...</b>\n\n"
    
    bot.answer_callback_query(call.id, f"📁 Отправляю {len(files)} файл(ов)...")
    
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=response,
        parse_mode='HTML'
    )

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

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад к заданиям", callback_data="back_to_dates"))
    markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    
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

# ===== ФУНКЦИИ ДЛЯ УЧИТЕЛЕЙ =====

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

# ===== ФУНКЦИИ ДЛЯ ДНЕЙ РОЖДЕНИЯ =====

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
        from main import cancel_operation
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
        from main import cancel_operation
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
        from main import cancel_operation
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

        from database import add_birthday_to_file
        success = add_birthday_to_file(name, month, day, added_by)

        if success:
            conn = sqlite3.connect('homework.db')
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO birthdays (name, month, day, added_by) VALUES (?, ?, ?, ?)',
                           (name, month, day, added_by))
            conn.commit()
            conn.close()

            del user_data[user_id]

            from database import get_month_name
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

def show_birthdays_for_month(call, month_num):
    from database import get_birthdays_by_month, get_month_name
    
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

# ===== ФУНКЦИИ ДЛЯ РЕШЕНИЙ =====

@bot.message_handler(commands=['solution'])
def solution_command(message):
    if not check_topic_access(message):
        return

    user_id = message.from_user.id
    
    if len(message.text.split()) < 2:
        error_text = "❌ <b>Неверный формат команды!</b>\n\n"
        error_text += "Используйте: <code>/solution номер_задания</code>\n"
        error_text += "Например: <code>/solution 1</code>\n\n"
        error_text += "Номер задания можно увидеть при просмотре заданий на конкретную дату."
        
        if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
            bot.send_message(message.chat.id, error_text, parse_mode='HTML', message_thread_id=TOPIC_ID)
        else:
            bot.send_message(message.chat.id, error_text, parse_mode='HTML')
        return
    
    try:
        args = message.text.split()
        task_number = int(args[1])
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        conn = sqlite3.connect('homework.db')
        cursor = conn.cursor()
        
        cursor.execute('''
                       SELECT h.id, h.subject_name, h.date
                       FROM homework h
                       WHERE h.chat_id = ?
                       ORDER BY h.date, h.created_at
                       ''', (message.chat.id,))
        
        all_homework = cursor.fetchall()
        conn.close()
        
        if not all_homework:
            bot.send_message(message.chat.id, 
                           "📭 Нет доступных заданий для добавления решения.",
                           parse_mode='HTML')
            return
        
        if task_number < 1 or task_number > len(all_homework):
            error_text = f"❌ <b>Неверный номер задания!</b>\n\n"
            error_text += f"Доступно заданий: от 1 до {len(all_homework)}\n"
            error_text += "Используйте <code>/solution номер_задания</code>\n"
            bot.send_message(message.chat.id, error_text, parse_mode='HTML')
            return
        
        homework_id, subject_name, date_str = all_homework[task_number - 1]
        
        if user_id in user_data:
            del user_data[user_id]
        
        user_data[user_id] = {
            'step': 'waiting_solution_file',
            'homework_id': homework_id,
            'subject_name': subject_name,
            'date': date_str,
            'added_by': f"{message.from_user.first_name or 'Аноним'}",
            'chat_id': message.chat.id,
            'topic_id': message.message_thread_id if hasattr(message, 'message_thread_id') else None,
            'files': [],
            'temp_files': []
        }
        
        log_action(message.from_user, "Начало добавления решения", 
                  f"Задание #{task_number}: {subject_name}, ID: {homework_id}")
        
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d.%m.%Y')
        except:
            formatted_date = date_str
        
        text = f"📝 <b>Добавление решения к заданию</b>\n\n"
        text += f"📚 <b>Предмет:</b> {subject_name}\n"
        text += f"📅 <b>Дата сдачи:</b> {formatted_date}\n"
        text += f"#️⃣ <b>Номер задания:</b> {task_number}\n\n"
        text += "📎 Отправьте файл с решением (документ, фото, аудио, видео):\n"
        text += "<i>Для завершения отправьте /done</i>\n"
        text += "<i>Для отмены отправьте /cancel</i>"
        
        if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
            bot.send_message(message.chat.id, text, parse_mode='HTML', message_thread_id=TOPIC_ID)
        else:
            bot.send_message(message.chat.id, text, parse_mode='HTML')
            
    except ValueError:
        error_text = "❌ <b>Неверный номер задания!</b>\n\n"
        error_text += "Номер должен быть целым числом.\n"
        error_text += "Используйте: <code>/solution номер_задания</code>\n"
        bot.send_message(message.chat.id, error_text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка в команде /solution: {e}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка при обработке команды.", parse_mode='HTML')

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

def send_error(message, text):
    if message.chat.type in ['group', 'supergroup'] and TOPIC_ID is not None:
        bot.send_message(message.chat.id, text, message_thread_id=TOPIC_ID)
    else:
        bot.send_message(message.chat.id, text)