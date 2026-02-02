# migrate_files.py
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILES_DIR = os.path.join(BASE_DIR, 'homework_files')

conn = sqlite3.connect('homework.db')
cursor = conn.cursor()

# Создаем новую таблицу с правильной структурой
cursor.execute('''
    CREATE TABLE IF NOT EXISTS homework_files_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        homework_id INTEGER,
        file_name TEXT NOT NULL,
        file_type TEXT NOT NULL,
        original_name TEXT,
        added_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (homework_id) REFERENCES homework(id) ON DELETE CASCADE
    )
''')

# Переносим данные из старой таблицы
cursor.execute('SELECT id, file_path, file_type, file_name, added_by FROM homework_files')
old_files = cursor.fetchall()

for file_id, file_path, file_type, old_file_name, added_by in old_files:
    # Извлекаем имя файла из пути
    if file_path:
        # Обрабатываем разные форматы путей
        if 'homework\\files\\' in file_path:
            filename = file_path.split('homework\\files\\')[-1]
        elif 'homework_files\\' in file_path:
            filename = file_path.split('homework_files\\')[-1]
        elif '/' in file_path:
            filename = file_path.split('/')[-1]
        else:
            filename = file_path
        
        # Проверяем, существует ли файл
        file_path_full = os.path.join(FILES_DIR, filename)
        if os.path.exists(file_path_full):
            cursor.execute('''
                INSERT INTO homework_files_new (homework_id, file_name, file_type, original_name, added_by)
                VALUES (?, ?, ?, ?, ?)
            ''', (file_id, filename, file_type, old_file_name or filename, added_by))
            print(f"Перенесен файл: {filename}")
        else:
            print(f"Файл не найден: {filename}")

# Переименовываем таблицы
cursor.execute('DROP TABLE IF EXISTS homework_files_old')
cursor.execute('ALTER TABLE homework_files RENAME TO homework_files_old')
cursor.execute('ALTER TABLE homework_files_new RENAME TO homework_files')

conn.commit()
conn.close()
print("Миграция завершена!")
