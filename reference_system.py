import logging
from telebot import types

logger = logging.getLogger(__name__)

def show_reference_folders(call):
    bot = call.bot
    bot.answer_callback_query(call.id, "Функция в разработке")

def start_create_reference_folder(message):
    pass

def show_folders_for_adding_files(call):
    pass

def search_reference_materials(call):
    pass

def show_folder_files(call, folder_id):
    pass

def start_add_files_to_folder(call, folder_id):
    pass

def request_files_range(call, folder_id):
    pass

def send_selected_files(call, folder_id, start_range, end_range):
    pass

def delete_reference_folder(call, folder_id):
    pass

def process_reference_file(message, user_id, content_type, file_type, default_name):
    pass