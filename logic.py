import sqlite3
from datetime import datetime
import os
import cv2
import threading 

from config import DATABASE 


class DatabaseManager:
    def __init__(self, database):
        self.database = database
        self.lock = threading.RLock() # Использование RLock для синхронизации доступа к БД из разных потоков

    def create_tables(self):
        with self.lock:
            conn = sqlite3.connect(self.database)
            with conn:
                conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    user_name TEXT
                )
            ''')

                conn.execute('''
                CREATE TABLE IF NOT EXISTS prizes (
                    prize_id INTEGER PRIMARY KEY,
                    image TEXT,
                    used INTEGER DEFAULT 0
                )
            ''')

                conn.execute('''
                CREATE TABLE IF NOT EXISTS winners (
                    user_id INTEGER,
                    prize_id INTEGER,
                    win_time TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(user_id),
                    FOREIGN KEY(prize_id) REFERENCES prizes(prize_id)
                )
            ''')

                conn.commit()

    def add_user(self, user_id, user_name):
        with self.lock:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
                if cur.fetchone() is None:
                    conn.execute('INSERT INTO users VALUES (?, ?)', (user_id, user_name))
                    conn.commit()
                    return True
                else:
                    return False


    def add_prize(self, data):
        with self.lock:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM prizes")
                if cur.fetchone()[0] == 0:
                    conn.executemany('''INSERT INTO prizes (image) VALUES (?)''', data)
                    conn.commit()


    def add_winner(self, user_id, prize_id):
        win_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self.lock:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM winners WHERE user_id = ? AND prize_id = ?", (user_id, prize_id))
                if cur.fetchall():
                    return 0
                else:
                    cur.execute("SELECT used FROM prizes WHERE prize_id = ?", (prize_id,))
                    prize_status = cur.fetchone()
                    if prize_status and prize_status[0] == 0:
                        conn.execute('''INSERT INTO winners (user_id, prize_id, win_time) VALUES (?, ?, ?)''', (user_id, prize_id, win_time))
                        conn.execute('''UPDATE prizes SET used = 1 WHERE prize_id = ?''', (prize_id,))
                        conn.commit()
                        return 1
                    else:
                         return -1


    def mark_prize_used(self, prize_id):
        with self.lock:
            conn = sqlite3.connect(self.database)
            with conn:
                conn.execute('''UPDATE prizes SET used = 1 WHERE prize_id = ?''', (prize_id,))
                conn.commit()


    def get_users(self):
        with self.lock:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()
                cur.execute('SELECT user_id FROM users')
                return [x[0] for x in cur.fetchall()]


    def get_prize_img(self, prize_id):
        with self.lock:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()
                cur.execute('SELECT image FROM prizes WHERE prize_id = ?', (prize_id,))
                result = cur.fetchone()
                if result:
                    return result[0]
                else:
                    return None


    def get_random_prize(self):
        with self.lock:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()
                cur.execute('SELECT prize_id, image FROM prizes WHERE used = 0 ORDER BY RANDOM() LIMIT 1')
                result = cur.fetchone()
                return result

    # Методы для проверки получения всех призов
    def get_total_prizes_count(self):
        with self.lock:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()
                cur.execute('SELECT COUNT(*) FROM prizes')
                count = cur.fetchone()[0]
                return count

    def get_user_won_prizes_count(self, user_id):
        with self.lock:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()
                cur.execute('SELECT COUNT(DISTINCT prize_id) FROM winners WHERE user_id = ?', (user_id,))
                count = cur.fetchone()[0]
                return count


def hide_img(img_name):
    os.makedirs('hidden_img', exist_ok=True)
    image_path = f'img/{img_name}'
    if not os.path.exists(image_path):
        print(f"Error: Source image file not found: {image_path}")
        return

    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not read image {image_path}. Check file format/corruption.")
        return

    blurred_image = cv2.GaussianBlur(image, (15, 15), 0)
    if blurred_image.shape[0] > 0 and blurred_image.shape[1] > 0:
        pixelated_image = cv2.resize(blurred_image, (30, 30), interpolation=cv2.INTER_NEAREST)
        pixelated_image = cv2.resize(pixelated_image, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
        output_path = f'hidden_img/{img_name}'
        cv2.imwrite(output_path, pixelated_image)
    else:
        print(f"Error: Invalid dimensions for image {image_path}")


if __name__ == '__main__':
    # Этот блок оставлен для возможности отдельного тестирования logic.py
    # Для работы бота он не используется.
    if not os.path.exists('config.py'):
        with open('config.py', 'w') as f:
            f.write("DATABASE = 'telegram_bot.db'\n")
            print("Создан файл config.py-заглушка")
        try:
            from config import DATABASE
        except ImportError:
            print("Ошибка импорта config.py после создания. Убедитесь, что файл создан корректно.")
            exit()

    if not os.path.exists('img'):
        os.makedirs('img')
        print("Создан каталог 'img'. Пожалуйста, добавьте файлы изображений (.png, .jpg) в каталог 'img'.")


    print(f"Используется файл базы данных: {DATABASE}")
    manager = DatabaseManager(DATABASE)

    manager.create_tables()
    prizes_img = []
    if os.path.exists('img'):
         prizes_img = [f for f in os.listdir('img') if os.path.isfile(os.path.join('img', f))]

    data = [(x,) for x in prizes_img]

    print("\nНастройка базы данных завершена.")
    print(f"Таблицы созданы/проверены в {DATABASE}.")

    print("\n--- Тестирование методов ---")

    print("Добавление фиктивных пользователей...")
    manager.add_user(101, "Alice")
    manager.add_user(102, "Bob")
    added_alice_again = manager.add_user(101, "Alice")
    print(f"Попытка добавить Alice снова: {added_alice_again}")
    print("Пользователи добавлены.")

    users = manager.get_users()
    print(f"Зарегистрированные ID пользователей: {users}")

    print("\nТестирование получения количества призов...")
    total_prizes = manager.get_total_prizes_count()
    print(f"Всего призов в БД: {total_prizes}")

    user_won_count_101 = manager.get_user_won_prizes_count(101)
    print(f"Пользователь 101 выиграл призов: {user_won_count_101}")


    print("\nПолучение случайного неиспользованного приза...")
    random_prize = manager.get_random_prize()
    if random_prize:
        prize_id, image_name = random_prize
        print(f"Найден случайный неиспользованный приз: ID={prize_id}, Изображение='{image_name}'")

        print(f"Получение имени изображения для приза с ID {prize_id}:")
        img_from_id = manager.get_prize_img(prize_id)
        print(f"Результат: '{img_from_id}'")

        print(f"\nСимулирование выдачи приза {prize_id} пользователю 101...")
        add_winner_status = manager.add_winner(101, prize_id)
        if add_winner_status == 1:
            print("Победитель добавлен, приз отмечен как использованный.")
            user_won_count_101 = manager.get_user_won_prizes_count(101)
            print(f"После выигрыша, пользователь 101 выиграл призов: {user_won_count_101}")
            if total_prizes > 0 and user_won_count_101 >= total_prizes:
                print("Тестовое сообщение: Пользователь 101 получил все доступные призы!")

        elif add_winner_status == 0:
             print("Пользователь 101 уже выиграл этот приз.")
        elif add_winner_status == -1:
             print("Приз не найден или уже использован.")

        print("\nПопытка получить еще один случайный неиспользованный приз (после использования первого)...")
        random_prize_after_use = manager.get_random_prize()
        if random_prize_after_use:
            print(f"Найден еще один случайный неиспользованный приз: {random_prize_after_use}")
        else:
            print("Не осталось неиспользованных призов (или существовал только один и он был использован).")

    else:
        print("Не осталось неиспользованных призов в базе данных.")

    print("\n--- Конец тестирования ---")
    print("Проверьте свою папку на наличие файла базы данных (например, telegram_bot.db) и убедитесь, что таблица 'prizes' заполнена.")