import sqlite3
from datetime import datetime
import os
import cv2
import threading
import numpy as np
import math 

try:
    from config import DATABASE
except ImportError:
    DATABASE = None
    print("Предупреждение: файл config.py не найден. Он требуется для работы бота.")

class DatabaseManager:
    def __init__(self, database):
        if not database:
            raise ValueError("Путь к базе данных не указан при создании DatabaseManager.")
        self.database = database
        self.lock = threading.RLock()

    def create_tables(self):
        with self.lock:
            db_dir = os.path.dirname(self.database)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)

        conn = None
        try:
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
                    win_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    prize_id INTEGER,
                    win_time TEXT,
                    UNIQUE(user_id, prize_id),
                    FOREIGN KEY(user_id) REFERENCES users(user_id),
                    FOREIGN KEY(prize_id) REFERENCES prizes(prize_id)
                )
            ''')
        except sqlite3.Error as e:
            print(f"Ошибка при создании таблиц: {e}")


    def add_user(self, user_id, user_name):
        with self.lock:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
                if cur.fetchone() is None:
                    cur.execute('INSERT OR IGNORE INTO users (user_id, user_name) VALUES (?, ?)', (user_id, user_name))
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
                count = cur.fetchone()[0]
                if count == 0:
                    cur.executemany('''INSERT OR IGNORE INTO prizes (image) VALUES (?)''', data)
                    added_count = cur.rowcount
                    conn.commit()
                    print(f"Попытка добавить {len(data)} призов. Добавлено новых: {added_count}")


    def add_winner(self, user_id, prize_id):
        
        #Добавляет запись о выигрыше для пользователя и приза. Возвращает:
        # 1: Успешно добавлен (приз был доступен, лимит не превышен)
        # 0: Этот пользователь уже выигрывал этот приз (повторная попытка получить тот же при)
        # -1: Приз не найден или лимит призов достигнут другими пользователями
        # -2: Системная, непредвиденная ошибка.

        # Возможные причины -2: Повреждение файла базы данных. Ошибки с разрешениями на запись в файл базы данных. Любая другая внутренняя ошибка Python или SQLite, которая не связана напрямую с логикой выигрыша приза (1,0,-1).
        
        win_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        PRIZE_LIMIT = 3 # Максимальное количество победителей для одного приза

        with self.lock:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()

                try:
                    cur.execute("SELECT prize_id, used FROM prizes WHERE prize_id = ?", (prize_id,))
                    prize_info = cur.fetchone()

                    if prize_info is None:
                        return -1 

                    cur.execute("SELECT 1 FROM winners WHERE user_id = ? AND prize_id = ?", (user_id, prize_id))
                    if cur.fetchone():
                        return 0 

                    
                    prize_id_check, prize_globally_used_status = prize_info 

                    if prize_globally_used_status == 1:
                        return -1 

                    cur.execute("SELECT COUNT(DISTINCT user_id) FROM winners WHERE prize_id = ?", (prize_id,))
                    current_winners_count_for_prize = cur.fetchone()[0]

                    if current_winners_count_for_prize >= PRIZE_LIMIT:
                        if prize_globally_used_status == 0:
                            cur.execute('''UPDATE prizes SET used = 1 WHERE prize_id = ?''', (prize_id,))
                            conn.commit() 
                        return -1

                    cur.execute('''
                        INSERT INTO winners (user_id, prize_id, win_time)
                        VALUES (?, ?, ?)
                    ''', (user_id, prize_id, win_time))
                    
                    new_total_winners_for_prize = current_winners_count_for_prize + 1

                    if new_total_winners_for_prize >= PRIZE_LIMIT:
                        if prize_globally_used_status == 0:
                             cur.execute('''UPDATE prizes SET used = 1 WHERE prize_id = ?''', (prize_id,))

                    conn.commit()
                    return 1 

                except sqlite3.IntegrityError:
                    print(f"add_winner: IntegrityError (вероятно, гонка или повторная попытка) для user {user_id}, prize {prize_id}. Возвращаем 0.")
                    return 0

                except Exception as e:
                    print(f"add_winner: Неожиданная ошибка для пользователя {user_id}, приза {prize_id}: {e}")
                    return -2 # Возвращается, если во время выполнения операции add_winner возникла непредвиденная ошибка (Exception), которая не была явно обработана (например, не sqlite3.IntegrityError).


    def mark_prize_used(self, prize_id):
        with self.lock:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()
                cur.execute('''UPDATE prizes SET used = 1 WHERE prize_id = ?''', (prize_id,))
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

    def get_all_prize_images(self):
        with self.lock:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()
                cur.execute('SELECT image FROM prizes')
                return [x[0] for x in cur.fetchall()]

    def get_winners_img(self, user_id):
        with self.lock:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()
                cur.execute('''
                    SELECT p.image FROM winners w
                    INNER JOIN prizes p ON w.prize_id = p.prize_id
                    WHERE w.user_id = ?
                ''', (user_id,))
                return cur.fetchall()


    def get_random_prize(self):
        with self.lock:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()
                cur.execute('SELECT prize_id, image FROM prizes WHERE used = 0 ORDER BY RANDOM() LIMIT 1')
                result = cur.fetchone()
                return result

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

    def get_winners_count(self, prize_id):
        with self.lock:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(DISTINCT user_id) FROM winners WHERE prize_id = ?", (prize_id,))
                count = cur.fetchone()[0]
                return count

    def get_rating(self):
        with self.lock:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()
                cur.execute('''
                    SELECT u.user_name, COUNT(DISTINCT w.prize_id) AS prize_count
                    FROM users AS u
                    JOIN winners AS w ON u.user_id = w.user_id
                    GROUP BY u.user_id, u.user_name
                    ORDER BY prize_count DESC
                    LIMIT 10
                ''')
                results = cur.fetchall()
                return results


def hide_img(img_name):
    os.makedirs('hidden_img', exist_ok=True)
    image_path = f'img/{img_name}'

    if not os.path.exists(image_path):
        print(f"Ошибка [hide_img]: Исходный файл изображения не найден: {image_path}")
        return

    image = cv2.imread(image_path)

    if image is None:
        print(f"Ошибка [hide_img]: Не удалось прочитать изображение {image_path}.")
        return

    if image.shape[0] == 0 or image.shape[1] == 0:
        print(f"Ошибка [hide_img]: Изображение {image_path} имеет нулевые размеры.")
        return

    try:
        small_img = cv2.resize(image, (30, 30), interpolation=cv2.INTER_NEAREST)
        pixelated_image = cv2.resize(small_img, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
        output_path = f'hidden_img/{img_name}'
        cv2.imwrite(output_path, pixelated_image)
    except Exception as e:
        print(f"Ошибка [hide_img]: во время обработки изображения для {image_path}: {e}")

def create_collage(user_id, manager):
    all_prize_filenames = manager.get_all_prize_images() 
    won_prize_info = manager.get_winners_img(user_id) 

    won_filenames_set = {x[0] for x in won_prize_info}

    if not all_prize_filenames:
        print("Нет призов в базе данных для создания коллажа.")
        return None 

    images_for_collage = []
    target_cell_size = (256, 256) 

    for img_filename in all_prize_filenames:
        img_path = ''
        if img_filename in won_filenames_set:
            img_path = os.path.join('img', img_filename)
        else:
            hide_img(img_filename)
            img_path = os.path.join('hidden_img', img_filename)

        img = None
        if os.path.exists(img_path):
            img = cv2.imread(img_path)

        if img is None:
            print(f"Предупреждение: Не удалось загрузить изображение для коллажа: {img_path}. Использование черного плейсхолдера.")
            img = np.zeros((*target_cell_size, 3), dtype=np.uint8)
        else:
            img = cv2.resize(img, target_cell_size, interpolation=cv2.INTER_AREA)

        images_for_collage.append(img)

    num_images = len(images_for_collage)
    if num_images == 0:
        return None 

    num_cols = math.floor(math.sqrt(num_images))
    if num_cols == 0: 
        num_cols = 1
    num_rows = math.ceil(num_images / num_cols)

    cell_height, cell_width, _ = images_for_collage[0].shape

    collage_width = num_cols * cell_width
    collage_height = num_rows * cell_height
    collage = np.zeros((collage_height, collage_width, 3), dtype=np.uint8)

    for i, image in enumerate(images_for_collage):
        row = i // num_cols
        col = i % num_cols

        if image.shape[0] != cell_height or image.shape[1] != cell_width:
             image = cv2.resize(image, (cell_width, cell_height), interpolation=cv2.INTER_AREA)

        collage[row * cell_height:(row + 1) * cell_height,
                col * cell_width:(col + 1) * cell_width] = image

    return collage


# --- Блок для отдельного тестирования logic.py ---
# Здесь вы можете проверить работу logic.py, используя отдельную БД (Во время теста в папке созздастся файл test_collage_101.png, его можно удалить после окончания теста.)

if __name__ == '__main__':
    print("--- Запуск тестирования logic.py ---")

    TEST_DATABASE = 'test_telegram_bot.db'
    PRIZE_LIMIT_TEST = 3

    if os.path.exists(TEST_DATABASE):
        try:
            os.remove(TEST_DATABASE)
            print(f"Удалена старая тестовая база данных: {TEST_DATABASE}")
        except OSError as e:
            print(f"Ошибка при удалении старой тестовой базы данных {TEST_DATABASE}: {e}")

    img_dir = 'img'
    if not os.path.exists(img_dir):
        os.makedirs(img_dir)
        print(f"Создан каталог '{img_dir}'. Пожалуйста, добавьте файлы изображений (.png, .jpg) в него.")

    fake_prizes_list = ['fake_prize_1.png', 'fake_prize_2.jpg', 'fake_prize_3.png', 'fake_prize_4.jpg', 'fake_prize_5.png', 'fake_prize_6.png', 'fake_prize_7.jpg']
    has_real_images = any(f.lower().endswith(('.png', '.jpg', '.jpeg')) for f in os.listdir(img_dir) if os.path.isfile(os.path.join(img_dir, f)))

    if not has_real_images:
        print(f"Каталог '{img_dir}' не содержит стандартных изображений. Создаем фиктивные файлы для тестирования призов.")
        try:
            for fname in fake_prizes_list:
                fpath = os.path.join(img_dir, fname)
                dummy_image = np.zeros((10, 10, 3), dtype=np.uint8)
                cv2.imwrite(fpath, dummy_image)
            print(f"Созданы фиктивные файлы призов в '{img_dir}'.")
        except ImportError:
            print("Numpy не найден. Невозможно создать фиктивные изображения.")
        except Exception as e:
            print(f"Ошибка при создании фиктивных изображений: {e}")
    else:
        print(f"Каталог '{img_dir}' содержит файлы изображений. Используем их.")


    manager = DatabaseManager(TEST_DATABASE)

    print("\nНастройка базы данных...")
    manager.create_tables()
    print("Таблицы созданы/проверены (в тестовой БД).")

    prizes_img = [f for f in os.listdir(img_dir) if os.path.isfile(os.path.join(img_dir, f)) and f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    data = [(x,) for x in prizes_img]
    if data:
        manager.add_prize(data)
    else:
        print("Внимание: Нет файлов изображений в 'img'. Невозможно добавить призы в тестовую БД.")

    total_prizes = manager.get_total_prizes_count()
    print(f"Всего призов в БД после добавления из '{img_dir}': {total_prizes}")
    if total_prizes == 0:
        print("Внимание: В тестовой БД нет призов. Тестирование выигрышей и рейтинга будет ограничено.")


    print("\nДобавление тестовых пользователей...")
    test_users = {
        101: "Alice", 102: "Bob", 103: "Charlie", 104: "David",
        105: "Eve", 106: "Frank", 107: "Grace", 108: "Heidi", 109: "Ivan", 110: "Judy",
        5001337549: "LargeIDUser"
    }

    for user_id, user_name in test_users.items():
        added = manager.add_user(user_id, user_name)
        print(f"Попытка добавить пользователя ID {user_id} ('{user_name}'): {'Успех' if added else 'Уже существует'}")

    users_in_db = manager.get_users()
    print(f"Зарегистрированные ID пользователей: {users_in_db}")

    print("\nСимулирование выигрышей...")
    available_prizes_raw = []
    available_prize_ids = []
    with manager.lock:
        conn = sqlite3.connect(manager.database)
        with conn:
            cur = conn.cursor()
            cur.execute('SELECT prize_id, image FROM prizes')
            available_prizes_raw = cur.fetchall()
            available_prize_ids = [p[0] for p in available_prizes_raw]
            print(f"Все ID призов для симуляции: {available_prize_ids}")


    simulated_prize_used_status = {}
    simulated_winners_count_by_prize = {}
    simulated_user_unique_wins = {}

    for prize_id, _ in available_prizes_raw:
        simulated_prize_used_status[prize_id] = False
        simulated_winners_count_by_prize[prize_id] = set()

    for user_id in test_users.keys():
        simulated_user_unique_wins[user_id] = set()


    wins_to_simulate = []

    if len(available_prize_ids) >= 3:
        prize_A = available_prize_ids[0]
        prize_B = available_prize_ids[1]
        prize_C = available_prize_ids[2]

        print(f"\n--- Тестирование лимита призов для Приза ID {prize_A} (Лимит: {PRIZE_LIMIT_TEST}) ---")
        wins_to_simulate.extend([
            (101, prize_A), # Alice выигрывает Приз A (1/3) -> Ожидается 1
            (102, prize_A), # Bob выигрывает Приз A (2/3) -> Ожидается 1
            (103, prize_A), # Charlie выигрывает Приз A (3/3) -> Ожидается 1 (Приз A становится 'used')
            (104, prize_A), # David пытается выиграть Приз A (Лимит достигнут) -> Ожидается -1
            (101, prize_A), # Alice пытается выиграть Приз A снова (Уже выиграла) -> Ожидается 0
            (5001337549, prize_A), # LargeIDUser пытается выиграть Приз A (Лимит достигнут) -> Ожидается -1
        ])

        print(f"\n--- Тестирование различных выигрышей для рейтинга ---")
        wins_to_simulate.extend([
            (101, prize_B), # Alice выигрывает Приз B (1/3) -> Ожидается 1 (У Alice теперь 2 уникальных приза)
            (104, prize_B), # David выигрывает Приз B (1/3) -> Ожидается 1
            (105, prize_B), # Eve выигрывает Приз B (2/3) -> Ожидается 1

            (101, prize_C), # Alice выигрывает Приз C (1/3) -> Ожидается 1 (У Alice теперь 3 уникальных приза)
            (106, prize_C), # Frank выигрывает Приз C (1/3) -> Ожидается 1
            (107, prize_C), # Grace выигрывает Приз C (1/3) -> Ожидается 1 (Приз C становится 'used')
        ])

        if len(available_prize_ids) >= 4:
            prize_D = available_prize_ids[3]
            wins_to_simulate.extend([
                (102, prize_D), # Bob выигрывает Приз D (1/3) -> Ожидается 1 (У Bob теперь 2 уникальных приза)
                (108, prize_D), # Heidi выигрывает Приз D (1/3) -> Ожидается 1
                (109, prize_D), # Ivan выигрывает Приз D (1/3) -> Ожидается 1 (Приз D становится 'used')
            ])

        if len(available_prize_ids) >= 5:
            prize_E = available_prize_ids[4]
            wins_to_simulate.extend([
                (101, prize_E), # Alice выигрывает Приз E (1/3) -> Ожидается 1 (У Alice теперь 4 уникальных приза)
                (110, prize_E), # Judy выигрывает Приз E (1/3) -> Ожидается 1
            ])
    else:
        print("Недостаточно призов (минимум 3) для полной симуляции выигрышей.")


    print("\nНачало симуляции выигрышей...")
    for user_id, prize_id_to_win in wins_to_simulate:
        print(f"\nПопытка: Пользователь {user_id} выигрывает Приз ID {prize_id_to_win}...")

        expected_status = None

        if prize_id_to_win not in simulated_prize_used_status:
            expected_status = -1
        else:
            if user_id in simulated_user_unique_wins and prize_id_to_win in simulated_user_unique_wins[user_id]:
                expected_status = 0
            else:
                current_sim_winners_for_prize = len(simulated_winners_count_by_prize.get(prize_id_to_win, set()))

                if simulated_prize_used_status[prize_id_to_win] or current_sim_winners_for_prize >= PRIZE_LIMIT_TEST:
                    expected_status = -1
                else:
                    expected_status = 1
                    simulated_user_unique_wins.setdefault(user_id, set()).add(prize_id_to_win)
                    simulated_winners_count_by_prize[prize_id_to_win].add(user_id)

                    if len(simulated_winners_count_by_prize[prize_id_to_win]) == PRIZE_LIMIT_TEST:
                        simulated_prize_used_status[prize_id_to_win] = True

        actual_status = manager.add_winner(user_id, prize_id_to_win)
        print(f"  Результат add_winner (фактический): {actual_status}")

        assert actual_status == expected_status, f"Несоответствие для пользователя {user_id}, приза {prize_id_to_win}. Ожидалось {expected_status}, получено {actual_status}."


    print("\n--- Тестирование метода get_winners_count ---")
    if available_prizes_raw:
        for prize_id, _ in available_prizes_raw:
            expected_count = len(simulated_winners_count_by_prize.get(prize_id, set()))
            actual_count = manager.get_winners_count(prize_id)
            print(f"Приз ID {prize_id}: Ожидается {expected_count} уникальных победителей, Получено {actual_count}.")
            assert actual_count == expected_count, f"Ошибка в get_winners_count для приза {prize_id}: Ожидалось {expected_count}, получено {actual_count}"

        prize_id_not_in_db = 999999
        actual_count_not_won = manager.get_winners_count(prize_id_not_in_db)
        print(f"Приз ID {prize_id_not_in_db} (несуществующий): Ожидается 0 победителей, Получено {actual_count_not_won}.")
        assert actual_count_not_won == 0, f"Ошибка в get_winners_count для несуществующего приза {prize_id_not_in_db}"
    else:
        print("Нет доступных призов для тестирования get_winners_count.")


    print("\n--- Тестирование метода get_rating ---")
    rating_results = manager.get_rating()
    print("Полученный рейтинг (Топ-10):")
    if rating_results:
        assert isinstance(rating_results, list), "get_rating должен вернуть список"
        if rating_results:
            assert isinstance(rating_results[0], tuple) and len(rating_results[0]) == 2, "Каждый элемент рейтинга должен быть кортежем (user_name, prize_count)"

        for rank, (user_name, prize_count) in enumerate(rating_results):
            print(f"  {rank + 1}. {user_name}: {prize_count} приза(ов)")

        if len(rating_results) > 1:
            for i in range(len(rating_results) - 1):
                assert rating_results[i][1] >= rating_results[i+1][1], f"Ошибка сортировки в get_rating: {rating_results[i]} идет перед {rating_results[i+1]}"

        print("\nПроверка соответствия количества уникальных призов в рейтинге:")
        for user_name_in_rating, prize_count_in_rating in rating_results:
            found_user_id = None
            for uid, name in test_users.items():
                if name == user_name_in_rating:
                    found_user_id = uid
                    break

            if found_user_id is not None and found_user_id in simulated_user_unique_wins:
                expected_unique_count = len(simulated_user_unique_wins.get(found_user_id, set()))
                print(f"  Пользователь '{user_name_in_rating}' (ID: {found_user_id}): В рейтинге {prize_count_in_rating} призов, ожидается {expected_unique_count}.")
                assert prize_count_in_rating == expected_unique_count, f"Несоответствие уникальных призов для пользователя {user_name_in_rating} (ID: {found_user_id}). Ожидалось {expected_unique_count}, получено {prize_count_in_rating}"
    else:
        print("Нет данных для рейтинга (никто не выигрывал призы в симуляции).")

    print("\n--- Тестирование метода get_all_prize_images ---")
    all_prizes_from_db = manager.get_all_prize_images()
    print(f"Все призы из БД: {all_prizes_from_db}")
    if all_prizes_from_db:
        assert isinstance(all_prizes_from_db, list)
        assert isinstance(all_prizes_from_db[0], str)
    else:
        print("Нет призов для тестирования get_all_prize_images.")

    print("\n--- Тестирование метода get_winners_img ---")
    user_id_for_test = 101 # Alice
    alice_won_prizes = manager.get_winners_img(user_id_for_test)
    print(f"Призы, выигранные пользователем {user_id_for_test} (Alice): {alice_won_prizes}")
    if alice_won_prizes:
        assert isinstance(alice_won_prizes, list)
        assert isinstance(alice_won_prizes[0], tuple)
        assert isinstance(alice_won_prizes[0][0], str)
    else:
        print(f"Пользователь {user_id_for_test} не выиграл ни одного приза.")

    print("\n--- Тестирование hide_img (базовое) ---")
    if prizes_img:
        first_prize_img_name = prizes_img[0]
        print(f"Попытка создать скрытое изображение для '{first_prize_img_name}'...")
        hide_img(first_prize_img_name)
        hidden_path = f'hidden_img/{first_prize_img_name}'
        if os.path.exists(hidden_path):
            print(f"Успешно создано скрытое изображение: {hidden_path}")
        else:
            print(f"Ошибка: Не удалось создать скрытое изображение для '{first_prize_img_name}'. Проверьте логи выше.")
    else:
        print("Нет файлов изображений в 'img', тест hide_img пропущен.")
    
    print("\n--- Тестирование create_collage ---")
    if prizes_img:
        print(f"Создание коллажа для пользователя {user_id_for_test} (Alice)...")
        collage = create_collage(user_id_for_test, manager)
        if collage is not None:
            collage_output_path = f'test_collage_{user_id_for_test}.png'
            cv2.imwrite(collage_output_path, collage)
            print(f"Тестовый коллаж создан и сохранен как '{collage_output_path}'.")
        else:
            print(f"Не удалось создать коллаж для пользователя {user_id_for_test}.")
    else:
        print("Нет призов для тестирования create_collage.")


    print("\n--- Тестирование logic.py завершено ---")
    print(f"Тесты использовали базу данных: {TEST_DATABASE}")
