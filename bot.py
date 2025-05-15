from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from logic import *
import schedule
import threading
import time
import os
from config import * 


bot = TeleBot(API_TOKEN)

# Инициализируем DatabaseManager
manager = DatabaseManager(DATABASE)

# Убеждаемся, что таблицы созданы при запуске бота
manager.create_tables()

# Добавляем призы из каталога 'img' при запуске бота, если таблица пуста
try:
    if os.path.exists('img'):
        prizes_img = [f for f in os.listdir('img') if os.path.isfile(os.path.join('img', f))]
        data = [(x,) for x in prizes_img]

        if data:
            manager.add_prize(data)
            print(f"Попытка добавить {len(data)} призов из каталога 'img'.")
        else:
            print("Каталог 'img' пуст. Призы не добавлены.")
    else:
        print("Ошибка: Каталог 'img' не найден. Призы не могут быть добавлены. Создайте каталог 'img' и поместите туда изображения.")

except Exception as e:
    print(f"Произошла ошибка при добавлении призов из каталога 'img': {e}")


def gen_markup(prize_id):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("Получить!", callback_data=str(prize_id)))
    return markup

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    bot.answer_callback_query(call.id)

    try:
        prize_id = int(call.data)
    except ValueError:
        print(f"Некорректные данные обратного вызова: {call.data}")
        bot.send_message(call.message.chat.id, "Ошибка при обработке приза.")
        return

    user_id = call.message.chat.id

    add_status = manager.add_winner(user_id, prize_id)

    if add_status == 1:
        img_filename = manager.get_prize_img(prize_id)
        if img_filename:
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception as e:
                print(f"Не удалось удалить сообщение (возможно, пользователь сам его удалил): {e}")

            try:
                image_path = f'img/{img_filename}'
                if os.path.exists(image_path):
                     with open(image_path, 'rb') as photo:
                          bot.send_photo(user_id, photo, caption="Поздравляем! Вы получили этот приз!")
                else:
                     bot.send_message(user_id, "Поздравляем! Вы получили приз, но файл изображения не найден на сервере.")
                     print(f"Ошибка: Файл изображения приза не найден при отправке победителю: {image_path}")

            except Exception as e:
                 bot.send_message(user_id, f"Поздравляем! Вы получили приз, но произошла ошибка при отправке изображения: {e}")
                 print(f"Ошибка при отправке изображения победителю {user_id} приза {prize_id}: {e}")

            # Проверка на получение всех призов
            total_prizes_count = manager.get_total_prizes_count()
            user_won_count = manager.get_user_won_prizes_count(user_id)

            if total_prizes_count > 0 and user_won_count >= total_prizes_count:
                 bot.send_message(user_id, """🎉 Поздравляем! 🎉
Вы получили все доступные призы в этом розыгрыше!
Новых призов пока не будет. Следите за обновлениями бота - возможно, скоро появятся новые призы!""")
                 print(f"Пользователь {user_id} получил все {total_prizes_count} призов.")


    elif add_status == 0:
        try:
             bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Вы уже получили этот приз ранее.",
                reply_markup=None
            )
        except Exception as e:
            print(f"Не удалось отредактировать сообщение (уже получено ранее): {e}")
            bot.send_message(user_id, "Вы уже получили этот приз ранее.")


    elif add_status == -1:
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Увы, этот приз уже забрали :(",
                reply_markup=None
            )
        except Exception as e:
            print(f"Не удалось отредактировать сообщение (приз забран): {e}")
            bot.send_message(user_id, "Увы, этот приз уже забрали :(")


def send_message():
    available_prize = manager.get_random_prize()

    if available_prize:
        prize_id, img_filename = available_prize

        source_img_path = f'img/{img_filename}'
        hidden_img_path = f'hidden_img/{img_filename}'

        if not os.path.exists(source_img_path):
             print(f"Ошибка: Исходный файл приза не найден для скрытия: {source_img_path}. Пропуск отправки этого приза.")
             return

        hide_img(img_filename)

        if not os.path.exists(hidden_img_path):
             print(f"Ошибка: Не удалось создать скрытое изображение: {hidden_img_path}. Пропуск отправки этого приза.")
             return

        users = manager.get_users()
        if not users:
            print("Нет зарегистрированных пользователей для отправки приза.")
            return

        print(f"Отправка приза ID {prize_id} ({img_filename}) {len(users)} пользователям...")

        try:
            with open(hidden_img_path, 'rb') as photo_file:
                for user_id in users:
                    try:
                         bot.send_photo(user_id, photo_file, caption="Новый приз доступен! Успей получить!", reply_markup=gen_markup(prize_id))
                         photo_file.seek(0)

                    except Exception as e:
                         print(f"Не удалось отправить сообщение пользователю {user_id} для приза {prize_id}: {e}")

        except FileNotFoundError:
             print(f"Критическая ошибка: Файл скрытого изображения внезапно исчез: {hidden_img_path}")
        except Exception as e:
             print(f"Произошла общая ошибка при отправке скрытых изображений приза {prize_id}: {e}")

    else:
        print("Нет доступных неиспользованных призов для отправки.")


def shedule_thread():
    schedule.every(30).minutes.do(send_message) # Изменено на каждые 30 минут
    print("Планировщик запущен, отправка призов каждые 30 минут.")
    while True:
        schedule.run_pending()
        time.sleep(1)


@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.chat.id
    user_name = message.from_user.username if message.from_user.username else f"user_{user_id}"
    if manager.add_user(user_id, user_name):
        bot.reply_to(message, """Привет! Добро пожаловать!
Тебя успешно зарегистрировали!
Каждые 30 минут тебе будут приходить новые картинки и у тебя будет шанс их получить!
Для этого нужно быстрее всех нажать на кнопку 'Получить!'

Только три первых пользователя получат картинку!)""") # Обновлено сообщение о периодичности
    else:
        bot.reply_to(message, "Ты уже зарегистрирован!")


def polling_thread():
    print("Поллинг бота запущен...")
    bot.polling(none_stop=True, interval=2, timeout=20)


if __name__ == '__main__':
    # Инициализация менеджера, создание таблиц и добавление призов
    # выполняются в верхней части bot.py.

    polling_thread = threading.Thread(target=polling_thread)
    polling_thread.daemon = True
    polling_thread.start()

    shedule_thread = threading.Thread(target=shedule_thread)
    shedule_thread.daemon = True
    shedule_thread.start()

    print("Бот запущен. Нажмите Ctrl+C для остановки.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Остановка бота...")
    print("Бот остановлен.")