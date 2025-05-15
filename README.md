# A bot with prizes
In this bot, you will be able to get hold of exclusive pictures. But be vigilant, only 3 people can get them, and only once every 30 minutes!

# How does it work?
When you first write to the bot, it will register your account in the database.

![image](https://github.com/user-attachments/assets/091c436d-9503-4552-b38d-32a7ac4e385f)

When you have received a welcome message, all you have to do is wait for a new message from the bot:

![image](https://github.com/user-attachments/assets/8e19f187-01a2-4a57-afad-d178d43956b0)

After that, you have to hope that you have made it to the top three winners. The bot will send you a non-blurred picture, which will be the prize.

___________________________________________________________________________________________________________________________________________________

# What kind of data is the bot registering?

For those who are worried about a bot stealing personal data, I'll explain in more detail about how the database works.
When a new user messages the bot, the data is saved in the database so that their progress can be saved in the future and they don't have to re-register every time the /start command is sent. Here is a screenshot of what data is saved in the database:

![image](https://github.com/user-attachments/assets/2ffcb43a-5d98-4712-a7cf-d662f72d9da2)

1. user_id is the telegram account ID, which is not private information.
2. user_name - This is the nickname of your Telegram account, which is also not private.

This data is enough for the bot to remember you and be able to save progress.

# Surprise

When the user collects all the available prizes, a surprise awaits him... Try to collect all of them and see what happens
