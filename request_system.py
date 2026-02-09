import logging
from telebot import types

logger = logging.getLogger(__name__)

def start_request_add_files(call):
    pass

def show_pending_requests(call):
    pass

def handle_select_folder_for_request(call):
    pass

def show_request_details(call, request_id):
    pass

def preview_request_files(call, request_id):
    pass

def approve_request(call, request_id):
    pass

def reject_request(call, request_id):
    pass

def process_request_file(message, user_id, content_type, file_type, default_name):
    pass

def cancel_request_operation(message):
    pass