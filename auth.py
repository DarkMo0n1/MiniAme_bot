import logging
logger = logging.getLogger(__name__)

ADMIN_IDS = [1087190562, 5621181751, 2068653336]

def is_admin(user_id):
    logger.debug(f"Проверка администратора: user_id={user_id!r} (тип {type(user_id).__name__}), ADMIN_IDS={ADMIN_IDS}")
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        pass
    result = user_id in ADMIN_IDS
    logger.debug(f"Результат проверки: {result}")
    return result