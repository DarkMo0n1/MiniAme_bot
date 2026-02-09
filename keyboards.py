# keyboards.py
from telebot import types
from auth import is_admin

def create_main_menu():
    """Создает главное меню (доступно всем)"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton('📚 ДЗ', callback_data='homework_submenu'),
        types.InlineKeyboardButton('👨‍🏫 Учителя', callback_data='teacher_name_menu'),
        types.InlineKeyboardButton('🎂 Дни рождения', callback_data='birthdays_menu'),
        types.InlineKeyboardButton('📋 Ближайший зачёт', callback_data='exams_menu'),
        types.InlineKeyboardButton('📖 Справочные материалы', callback_data='reference_materials_menu'),
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

    markup.add(
        types.InlineKeyboardButton('📋 Все зачёты', callback_data='view_exams_menu'),
        types.InlineKeyboardButton('📅 Ближайшие зачёты', callback_data='upcoming_exams_menu')
    )

    if is_admin(user_id):
        markup.add(
            types.InlineKeyboardButton('📝 Добавить зачёт', callback_data='add_exam_menu'),
            types.InlineKeyboardButton('🗑️ Удалить зачёт', callback_data='delete_exam_menu')
        )

    markup.add(types.InlineKeyboardButton('🔙 Назад', callback_data='main_menu'))
    return markup

def create_reference_materials_menu(user_id):
    """Меню справочных материалов (разное для админа и обычных пользователей)"""
    markup = types.InlineKeyboardMarkup(row_width=2)

    markup.add(
        types.InlineKeyboardButton('📁 Просмотреть папки', callback_data='view_reference_folders'),
        types.InlineKeyboardButton('🔍 Поиск материалов', callback_data='search_reference_materials')
    )

    if not is_admin(user_id):
        markup.add(
            types.InlineKeyboardButton('📤 Запросить добавление файлов', callback_data='request_add_files')
        )

    if is_admin(user_id):
        markup.add(
            types.InlineKeyboardButton('📝 Создать папку', callback_data='create_reference_folder'),
            types.InlineKeyboardButton('📎 Добавить файлы', callback_data='add_reference_files'),
            types.InlineKeyboardButton('📋 Запросы на добавление', callback_data='view_pending_requests')
        )

    markup.add(types.InlineKeyboardButton('🔙 Назад', callback_data="main_menu"))
    return markup