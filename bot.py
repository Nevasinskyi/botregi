import os
import json
import secrets
import logging
import asyncio
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# Настройки Railway → Variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "8949636050:AAFhbh9RLFRgst78eNqJDOFtCs2ntokG5UI").strip()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://endearing-enchantment-production-c8a6.up.railway.app").rstrip("/")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "klatgram-hook-7x9p2k").strip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "fdgdsfdthfgetydftr667egdffhgdbvb")

BASE_DIR = Path(__file__).resolve().parent
USERS_FILE = BASE_DIR / "users.json"

# Защита файла от одновременных изменений в одном процессе
USERS_LOCK = asyncio.Lock()

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


# -------------------- ХРАНЕНИЕ НОМЕРОВ --------------------

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


async def safe_get_user_number(user_id):
    async with USERS_LOCK:
        return get_user_number(user_id)


async def safe_reserve_number(user_id):
    async with USERS_LOCK:
        return reserve_number(user_id)


async def safe_release_number(user_id):
    async with USERS_LOCK:
        return release_number(user_id)


# -------------------- МЕНЮ --------------------

def main_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "Получить номер",
                callback_data="get_number",
            )
        ],
        [
            InlineKeyboardButton(
                "Мой номер",
                callback_data="my_number",
            )
        ],
        [
            InlineKeyboardButton(
                "Освободить номер",
                callback_data="release_number",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# -------------------- КОМАНДЫ --------------------

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_message:
        await update.effective_message.reply_text(
            "KlatGram\n\nВыбери действие в меню ниже.",
            reply_markup=main_menu(),
        )


async def mynumber(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    if user is None or update.effective_message is None:
        return

    number = await safe_get_user_number(user.id)

    if number is None:
        message = (
            "У тебя пока нет закреплённого номера. "
            "Используй /start."
        )
    else:
        message = f"Твой выданный номер: {number}"

    await update.effective_message.reply_text(message)


async def release(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    if user is None or update.effective_message is None:
        return

    number = await safe_release_number(user.id)

    if number is None:
        message = "У тебя нет закреплённого номера."
    else:
        message = f"Номер {number} освобождён."

    await update.effective_message.reply_text(message)


# -------------------- КНОПКИ --------------------

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if query is None:
        return

    await query.answer()
    user_id = query.from_user.id

    if query.data == "get_number":
        number = await safe_reserve_number(user_id)

        if number is None:
            message = "Не удалось создать номер. Попробуй позже."
        else:
            message = (
                f"Твой номер: {number}\n\n"
                "Номер сохранён за твоим аккаунтом бота.\n"
                "Это сгенерированный идентификатор, а не настоящий "
                "номер телефона. Он не гарантирует возможность "
                "регистрации или получения SMS в KlatGram."
            )

    elif query.data == "my_number":
        number = await safe_get_user_number(user_id)

        if number:
            message = f"Твой номер: {number}"
        else:
            message = (
                "У тебя пока нет номера. "
                "Нажми «Получить номер»."
            )

    elif query.data == "release_number":
        number = await safe_release_number(user_id)

        if number:
            message = f"Номер {number} освобождён."
        else:
            message = "У тебя нет закреплённого номера."

    else:
        message = "Неизвестное действие."

    await query.edit_message_text(
        message,
        reply_markup=main_menu(),
    )


# -------------------- ОБРАБОТКА ОШИБОК --------------------

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logging.error(
        "Ошибка при обработке обновления",
        exc_info=context.error,
    )


# -------------------- ЗАПУСК WEBHOOK --------------------

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "Не задан BOT_TOKEN в переменных Railway."
        )

    if not WEBHOOK_URL.startswith("https://"):
        raise RuntimeError(
            "WEBHOOK_URL должен быть публичным HTTPS-доменом Railway."
        )

    if not WEBHOOK_PATH or "/" in WEBHOOK_PATH:
        raise RuntimeError(
            "WEBHOOK_PATH должен быть непустой строкой без слешей."
        )

    if not WEBHOOK_SECRET:
        raise RuntimeError(
            "Не задан WEBHOOK_SECRET в переменных Railway."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(8)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("mynumber", mynumber))
    application.add_handler(CommandHandler("release", release))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_error_handler(error_handler)

    port = int(os.getenv("PORT", "8080"))

    logging.info("Запуск KlatGram через webhook")

    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=WEBHOOK_PATH,
        webhook_url=f"{WEBHOOK_URL}/{WEBHOOK_PATH}",
        secret_token=WEBHOOK_SECRET,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
