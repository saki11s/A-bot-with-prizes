from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from logic import * 
import schedule
import threading
import time
import os
from datetime import datetime

try:
    from config import API_TOKEN, DATABASE
    
except ImportError:
    print("Ошибка: Не найден файл config.py или в нем отсутствуют API_TOKEN/DATABASE.")
    print("Создайте config.py и добавьте строки: API_TOKEN = 'ВАШ_ТОКЕН', DATABASE = 'telegram_bot.db'")
    exit()

bot = TeleBot(API_TOKEN)

manager = DatabaseManager(DATABASE)

manager.create_tables()

try:
    img_dir = 'img'
    if os.path.exists(img_dir):
        prizes_img = [f for f in os.listdir(img_dir) if os.path.isfile(os.path.join(img_dir, f)) and f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        data = [(x,) for x in prizes_img]

        if data:
            manager.add_prize(data)
        else:
            print(f"Каталог '{img_dir}' пуст или не содержит файлов изображений (.png, .jpg, .jpeg). Призы не добавлены.")
    else:
        print(f"Ошибка: Каталог '{img_dir}' не найден. Призы не могут быть добавлены. Создайте каталог '{img_dir}' и поместите туда изображения.")

except Exception as e:
    print(f"Произошла ошибка при добавлении призов из каталога '{img_dir}': {e}")


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
        bot.send_message(call.message.chat.id, "Произошла ошибка при обработке запроса приза. Попробуйте позже.")
        return

    user_id = call.message.chat.id 

    add_status = manager.add_winner(user_id, prize_id)

    if add_status == 1:
        img_filename = manager.get_prize_img(prize_id)
        if img_filename:
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception as e:
                print(f"Не удалось удалить сообщение {call.message.message_id} в чате {call.message.chat.id}: {e}")

            try:
                image_path = f'img/{img_filename}'
                if os.path.exists(image_path):
                     with open(image_path, 'rb') as photo:
                          bot.send_photo(user_id, photo, caption="Поздравляем! Вы получили этот приз!")
                     print(f"Пользователь {user_id} получил приз ID {prize_id}.")
                else:
                     bot.send_message(user_id, "Поздравляем! Вы получили приз, но файл изображения не найден на сервере.")
                     print(f"Ошибка: Файл изображения приза не найден на сервере при отправке победителю: {image_path} (Приз ID: {prize_id})")

            except Exception as e:
                 bot.send_message(user_id, f"Поздравляем! Вы получили приз, но произошла ошибка при отправке изображения: {e}")
                 print(f"Ошибка при отправке изображения победителю {user_id} приза {prize_id}: {e}")

            total_prizes_count = manager.get_total_prizes_count()
            user_won_count = manager.get_user_won_prizes_count(user_id)

            if total_prizes_count > 0 and user_won_count >= total_prizes_count:
                 bot.send_message(user_id, """🎉 Поздравляем! 🎉
Вы получили все доступные призы в этом розыгрыше!
Новых призов пока не будет. Следите за обновлениями бота - возможно, скоро появятся новые призы!""")
                 print(f"Пользователь {user_id} получил все {total_prizes_count} призов.")

        else:
             print(f"Ошибка: Имя файла изображения не найдено в БД для приза ID {prize_id} после успешного add_winner.")
             bot.send_message(user_id, "Поздравляем! Вы получили приз, но произошла внутренняя ошибка с изображением.")


    elif add_status == 0:
        print(f"Пользователь {user_id} уже получал приз ID {prize_id}.")
        try:
             bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Вы уже получили этот приз ранее.",
                reply_markup=None
            )
        except Exception as e:
            print(f"Не удалось отредактировать сообщение {call.message.message_id} (уже получено ранее): {e}")


    elif add_status == -1:
        print(f"Пользователь {user_id} пытался получить приз ID {prize_id}, который недоступен (-1).")
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Увы, этот приз уже забрали :(",
                reply_markup=None
            )
        except Exception as e:
            print(f"Не удалось отредактировать сообщение {call.message.message_id} (приз забран): {e}")


def send_message():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Планировщик: Попытка отправить новый приз.")

    available_prize = manager.get_random_prize()

    if available_prize:
        prize_id, img_filename = available_prize

        source_img_path = f'img/{img_filename}'
        hidden_img_path = f'hidden_img/{img_filename}'

        if not os.path.exists(source_img_path):
             print(f"Ошибка [send_message]: Исходный файл приза не найден: {source_img_path}. Пропуск отправки приза ID {prize_id}.")
             return

        try:
            hide_img(img_filename)
        except Exception as e:
            print(f"Ошибка [send_message]: при создании скрытого изображения для {img_filename} (Приз ID: {prize_id}): {e}. Пропуск отправки.")
            return

        if not os.path.exists(hidden_img_path):
             print(f"Ошибка [send_message]: Не удалось создать скрытое изображение: {hidden_img_path}. Пропуск отправки приза ID {prize_id}.")
             return
        users = manager.get_users()
        if not users:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Планировщик: Нет зарегистрированных пользователей для отправки приза.")
            return

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Планировщик: Отправка приза ID {prize_id} ({img_filename}) {len(users)} пользователям...")

        try:
            with open(hidden_img_path, 'rb') as photo_file:
                for user_id in users:
                    try:
                         photo_file.seek(0)
                         bot.send_photo(user_id, photo_file, caption="Новый приз доступен! Успей получить!", reply_markup=gen_markup(prize_id))

                    except Exception as e:
                         print(f"Ошибка [send_message]: Не удалось отправить сообщение пользователю {user_id} для приза {prize_id}: {e}")

        except FileNotFoundError:
             print(f"Критическая ошибка [send_message]: Файл скрытого изображения внезапно исчез: {hidden_img_path}. Пропуск отправки приза ID {prize_id}.")
        except Exception as e:
             print(f"Произошла общая ошибка [send_message]: при отправке скрытых изображений приза ID {prize_id}: {e}")
        finally:
            pass


    else:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Планировщик: Нет доступных неиспользованных призов для отправки.")


def shedule_thread():
    schedule.every(30).minutes.do(send_message)
    print("Планировщик запущен, отправка призов каждые 30 минут.")
    while True:
        schedule.run_pending()
        time.sleep(1)

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.chat.id
    user_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
    if not user_name:
        user_name = message.from_user.username or f"user_{user_id}"

    if manager.add_user(user_id, user_name):
        bot.reply_to(message, """Привет!
Тебя успешно зарегистрировали!
Каждые 30 минут тебе будут приходить новые картинки и у тебя будет шанс их получить!
Для этого нужно быстрее всех нажать на кнопку 'Получить!'

Только три первых пользователя получат картинку!)""")
        print(f"Новый пользователь зарегистрирован: ID={user_id}, Name='{user_name}'")
    else:
        bot.reply_to(message, "Ты уже зарегистрирован!")
        print(f"Пользователь {user_id} уже зарегистрирован.")

@bot.message_handler(commands=['rating'])
def handle_rating(message):
    print(f"Пользователь {message.chat.id} запросил рейтинг.")
    rating_list = manager.get_rating()

    if not rating_list:
        bot.reply_to(message, "Рейтинг пока пуст. Никто еще не выигрывал призы!")
        return

    rating_message = "🏆 Топ игроков по количеству уникальных призов: 🏆\n\n"
    for rank, (user_name, prize_count) in enumerate(rating_list):
        rating_message += f"{rank + 1}. {user_name}: {prize_count} приза(ов)\n"

    try:
        bot.send_message(
            message.chat.id,
            rating_message
        )
        print(f"Рейтинг успешно отправлен пользователю {message.chat.id}")
    except Exception as e:
        print(f"Ошибка при отправке рейтинга пользователю {message.chat.id}: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при получении рейтинга.")


@bot.message_handler(commands=['my_score'])
def handle_my_score(message):
    user_id = message.chat.id
    print(f"Пользователь {user_id} запросил коллаж призов.")

    collage_image = create_collage(user_id, manager)

    if collage_image is None:
        bot.reply_to(message, "Пока нет призов для создания коллажа, или произошла ошибка при его создании (возможно, в базе данных нет призов).")
        return

    temp_filename = f'collage_{user_id}.png'
    try:
        cv2.imwrite(temp_filename, collage_image)
        
        with open(temp_filename, 'rb') as photo:
            bot.send_photo(user_id, photo, caption="Ваш коллаж призов:")
        print(f"Коллаж отправлен пользователю {user_id}.")
    except Exception as e:
        print(f"Ошибка при отправке коллажа пользователю {user_id}: {e}")
        bot.reply_to(message, "Произошла ошибка при отправке коллажа. Попробуйте позже.")
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)


def polling_thread():
    print("Поллинг бота запущен...")
    bot.polling(none_stop=True, interval=2, timeout=20)


if __name__ == '__main__':

    polling_thread = threading.Thread(target=polling_thread)
    polling_thread.daemon = True
    polling_thread.start()

    shedule_thread = threading.Thread(target=shedule_thread)
    shedule_thread.daemon = True
    shedule_thread.start()

    print("Бот запущен. Потоки поллинга и планировщика стартовали.")
    print("Нажмите Ctrl+C для остановки.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Получен сигнал остановки (Ctrl+C)...")
    print("Бот остановлен.")
