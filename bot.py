import os
import json
import secrets
import logging
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8529279667:AAEiE7kuIVi-y85_6ZHOs2lYUwpbXgh5CgA")

BASE_DIR = Path(__file__).resolve().parent
USERS_FILE = BASE_DIR / "users.json"

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def load_users():
    if not USERS_FILE.exists():
        return {}

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        logging.exception("Не удалось прочитать users.json")
        return {}


def save_users(users):
    temp_file = USERS_FILE.with_suffix(".tmp")

    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump(users, file, ensure_ascii=False, indent=2)

    temp_file.replace(USERS_FILE)


def get_user_number(user_id):
    users = load_users()
    return users.get(str(user_id))


def reserve_number(user_id):
    users = load_users()
    user_id = str(user_id)

    if user_id in users:
        return users[user_id]

    used_numbers = set(users.values())

    # Генерируем уникальный номер из 11 цифр.
    for _ in range(10000):
        number = str(secrets.randbelow(9_000_000_000) + 1_000_000_000)

        if number not in used_numbers:
            users[user_id] = number
            save_users(users)
            return number

    return None


def release_number(user_id):
    users = load_users()
    number = users.pop(str(user_id), None)

    if number is not None:
        save_users(users)

    return number


def main_menu():
    keyboard = [
        [InlineKeyboardButton("Получить номер", callback_data="get_number")],
        [InlineKeyboardButton("Мой номер", callback_data="my_number")],
        [InlineKeyboardButton("Освободить номер", callback_data="release_number")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "KlatGram\n\n"
        "Выбери действие в меню ниже.",
        reply_markup=main_menu(),
    )


async def mynumber(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = get_user_number(update.effective_user.id)

    if number is None:
        message = "У тебя пока нет закреплённого номера. Используй /start."
    else:
        message = f"Твой выданный номер: {number}"

    await update.effective_message.reply_text(message)


async def release(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = release_number(update.effective_user.id)

    if number is None:
        message = "У тебя нет закреплённого номера."
    else:
        message = f"Номер {number} освобождён."

    await update.effective_message.reply_text(message)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data == "get_number":
        number = reserve_number(user_id)

        if number is None:
            message = "Не удалось создать номер. Попробуй позже."
        else:
            message = (
                f"Твой номер: {number}\n\n"
                "Он сохранён за твоим аккаунтом бота.\n"
                "Важно: это сгенерированный номер, а не подтверждение "
                "того, что сервер KlatGram его принимает."
            )

    elif query.data == "my_number":
        number = get_user_number(user_id)
        message = (
            f"Твой номер: {number}"
            if number
            else "У тебя пока нет номера. Нажми «Получить номер»."
        )

    elif query.data == "release_number":
        number = release_number(user_id)
        message = (
            f"Номер {number} освобождён."
            if number
            else "У тебя нет закреплённого номера."
        )

    else:
        message = "Неизвестное действие."

    await query.edit_message_text(message, reply_markup=main_menu())


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "Не задан BOT_TOKEN. Добавь его в переменные окружения."
        )

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("mynumber", mynumber))
    application.add_handler(CommandHandler("release", release))
    application.add_handler(CallbackQueryHandler(button_handler))

    logging.info("Бот запущен")
    application.run_polling()


if __name__ == "__main__":
    main()