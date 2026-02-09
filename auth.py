ADMIN_IDS = [1087190562, 5621181751, 2068653336]

def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS