import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILES_DIR = os.path.join(BASE_DIR, 'homework_files')

conn = sqlite3.connect('homework.db')
cursor = conn.cursor()

cursor.execute('SELECT id, file_path FROM homework_files')
files = cursor.fetchall()

for file_id, file_path in files:
    if 'homework\\files\\' in file_path:
        filename = file_path.split('homework\\files\\')[-1]
        new_path = os.path.join(FILES_DIR, filename)
        cursor.execute('UPDATE homework_files SET file_path = ? WHERE id = ?', (new_path, file_id))
        print(f"Обновлен файл {filename}")

conn.commit()
conn.close()
print("Пути в БД обновлены!")