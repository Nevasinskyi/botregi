import asyncio
import html
import random
import os
import time
import re
import psutil
from telethon.sessions import StringSession
from telethon import TelegramClient, events
from pathlib import Path


#ВСЯКАЯ ХУЙНЯ ИЗ ЗА КОТОРОЙ ВСЕ РАБОТАЕТ


API_ID = 37071915
API_HASH = '813aa290bbc1be070ff00f6ca8eb8a19'
OWNER_ID = 940460718
BASE_DIR = Path(__file__).resolve().parent
PHRASES_FILE = BASE_DIR / "phrases.txt"
PHOTOS_DIR = BASE_DIR / "photos"
BASE_DIR = Path(__file__).resolve().parent


selected_template = {}

пикми_enabled = True
пикми_enabled = False


#ЕБУЧИЙ ВХОД ПО СЕССИИ

bot = TelegramClient(
    StringSession(os.environ["TELEGRAM_SESSION"]),
    API_ID,
    API_HASH
)


#ЕБАННЫЕ ПЕРЕМЕННЫЕ


# targets:
# {
#     chat_id: {
#         user_id: {
#             'username': 'username'
#         }
#     }
# }

targets = {}

# Фото:
# {
#     user_id: 'путь к фото'
# }

target_photos = {}

processing = set()


# tag_tasks:
# {
#     chat_id: asyncio.Task
# }

tag_tasks = {}

# auto_tasks:
# {
#     (chat_id, username): asyncio.Task
# }

auto_tasks = {}

TEMPLATES_FILE = BASE_DIR / "templates.txt"

# Выбранный шаблон по ID чата
selected_templates = {}

# Автоответчики: (chat_id, user_id) -> текст шаблона
add_templates = {}


@bot.on(events.NewMessage(outgoing=True, pattern=r"^\.sb(?:\s+(\d+|reload))?$"))
async def select_template(event):
    if event.sender_id != OWNER_ID:
        return

    arg = event.pattern_match.group(1)
    templates = load_templates()

    if arg == "reload":
        await event.respond(f"Шаблоны обновлены. Найдено: {len(templates)}")
        return

    if not templates:
        await event.respond("Файл с шаблонами не найден или пуст.")
        return

    if arg is None:
        menu = "\n".join(
            f"{i}. {text}"
            for i, text in enumerate(templates, start=1)
        )
        await event.respond("⛧ ШАБЛОНЫ ⛧\n\n" + menu)
        return

    number = int(arg)

    if not 1 <= number <= len(templates):
        await event.respond(f"Укажи номер от 1 до {len(templates)}.")
        return

    selected_templates[event.chat_id] = templates[number - 1]
    await event.respond(
        f"Выбран шаблон №{number}:\n{templates[number - 1]}"
    )

pickme_enabled = False


#БЛЯДСКИЕ КОММАНДЫ КОТОРЫЕ УДАЛЯЮТСЯ


COMMAND_PATTERNS = [
    r'^\.startrp(?:\s+.*)?$',
    r'^\.unrp(?:\s+.*)?$',
    r'^\.list$',
    r'^\.clearrp$',
    r'^\.chatid$',
    r'^\.sb$',
    r'^\.sb reload$',
    r'^\.sb 1$',
    r'^\.sb 2$',
    r'^\.sb 3$',



    r'^\.add\s+.*$',
    r'^\.stopadd\s+.*$',

    r'^\.tagger(?:\s+.*)?$',
    r'^\.stoptagger$',

    r'^\.photo(?:\s+.*)?$',

    r'^\.menu$',
    r'^\.id$',

    r'^\.pickmeon$',
    r'^\.pickmeoff$',
]




 
# ==============================
# СОСТОЯНИЕ ПРОЦЕССА БОТА
# ==============================

import time
import os
import asyncio
import psutil

BOT_START_TIME = time.monotonic()


@bot.on(events.NewMessage(outgoing=True, pattern=r'^\.sys$'))
async def system_status_handler(event):
    if event.sender_id != OWNER_ID:
        return

    try:
        process = psutil.Process(os.getpid())
        cpu = await asyncio.to_thread(process.cpu_percent, interval=0.5)
        memory_mb = process.memory_info().rss / (1024 * 1024)

        uptime = int(time.monotonic() - BOT_START_TIME)
        days = uptime // 86400
        hours = (uptime % 86400) // 3600
        minutes = (uptime % 3600) // 60

        text = (
            "**⛧ Состояние системы ⛧**\n\n"
            f"⛧ ЦП бота: `{cpu:.1f}%`\n"
            f"⛧ ПАМЯТЬ бота: `{memory_mb:.1f} МБ`\n"
            f"⛧ система запущена: `{days}` дней "
            f"`{hours}` часов `{minutes}` минут"
        )

        await event.edit(text, parse_mode="md")

    except Exception as error:
        print(f"[SYS] Ошибка: {error}")
        await event.edit("Не удалось получить состояние бота.")


def load_templates():
    if not TEMPLATES_FILE.exists():
        return []

    return [
        line.strip()
        for line in TEMPLATES_FILE.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


# ==============================
# ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ УПРАВЛЕНИЯ
# ==============================

import re

# Настройки этого блока
CONTROL_PREFIX = "."
CONTROL_DELETE_LIMIT = 10
CONTROL_MAX_DELETE = 100

# Последние сообщения, отправленные самим аккаунтом
_last_own_message_id = None


def control_command(text):
    """Проверяет команду с текущим префиксом."""
    if not text:
        return None, ""

    prefix = CONTROL_PREFIX

    if not text.startswith(prefix):
        return None, ""

    parts = text[len(prefix):].strip().split(maxsplit=1)

    if not parts:
        return None, ""

    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    return command, args


@bot.on(events.NewMessage(outgoing=True))
async def control_commands_handler(event):
    global CONTROL_PREFIX
    global CONTROL_DELETE_LIMIT
    global _last_own_message_id

    # Только аккаунт владельца
    if event.sender_id != OWNER_ID:
        return

    text = event.raw_text or ""
    command, args = control_command(text)

    # Запоминаем обычные исходящие сообщения
    if command is None:
        _last_own_message_id = event.id
        return

    # Не обрабатываем команды в группах, если сообщение переслано
    if event.fwd_from:
        return

    # ------------------------------
    # .help
    # ------------------------------
    if command == "help":
        await event.edit(
            ".help — список команд\n"
            ".status — текущие настройки\n"
            ".del — удалить эту команду и последнее своё сообщение\n"
            ".clear 10 — удалить последние cвои сообщения\n"
            ".setlimit — изменить лимит команды .clear\n"
            ".prefix ! — изменить префикс команд\n"
            ".prefix . — вернуть точку\n"
            ".stopcontrol — выключить обработчик команд\n\n"
            "Примеры:\n"
            ".clear 5\n"
            ".setlimit 30\n"
            ".prefix !"
        )
        return

    # ------------------------------
    # .status
    # ------------------------------
    if command == "status":
        await event.edit(
            "СТАТУС УПРАВЛЕНИЯ\n\n"
            f"Префикс: {CONTROL_PREFIX}\n"
            f"Лимит удаления: {CONTROL_DELETE_LIMIT}\n"
            f"Максимальное удаление: {CONTROL_MAX_DELETE}\n"
            f"Последнее сохранённое ID: {_last_own_message_id}\n"
        )
        return

    # ------------------------------
    # .prefix ! / .prefix .
    # ------------------------------
    if command == "prefix":
        new_prefix = args.strip()

        if (
            len(new_prefix) != 1
            or new_prefix.isalnum()
            or new_prefix.isspace()
        ):
            await event.edit(
                "Укажи один не буквенно-цифровой символ.\n"
                "Пример: .prefix !"
            )
            return

        CONTROL_PREFIX = new_prefix

        await event.edit(
            f"Префикс изменён на: {CONTROL_PREFIX}\n"
            f"Теперь команда помощи: {CONTROL_PREFIX}help"
        )
        return


    # ------------------------------
    # .setlimit 20
    # ------------------------------
    if command == "setlimit":
        try:
            new_limit = int(args)
        except (TypeError, ValueError):
            await event.edit("Использование: .setlimit 20")
            return

        if not 1 <= new_limit <= CONTROL_MAX_DELETE:
            await event.edit(
                f"Лимит должен быть от 1 до {CONTROL_MAX_DELETE}."
            )
            return

        CONTROL_DELETE_LIMIT = new_limit
        await event.edit(f"Лимит удаления установлен: {new_limit}")
        return

    # ------------------------------
    # .clear 10
    # Удаляет последние свои сообщения в текущем чате
    # ------------------------------
    if command == "clear":
        try:
            amount = int(args) if args else CONTROL_DELETE_LIMIT
        except ValueError:
            await event.edit("Использование: .clear 10")
            return

        if not 1 <= amount <= CONTROL_MAX_DELETE:
            await event.edit(
                f"Укажи число от 1 до {CONTROL_MAX_DELETE}."
            )
            return

        chat = await event.get_input_chat()
        ids = []

        async for message in bot.iter_messages(chat, limit=amount + 1):
            if message.sender_id == OWNER_ID:
                ids.append(message.id)

        # Удаляем команду тоже, если она попала в выборку
        if event.id not in ids:
            ids.append(event.id)

        try:
            await bot.delete_messages(chat, ids)
        except Exception as error:
            print(f"[CONTROL] Ошибка удаления: {error}")
        return

    # ------------------------------
    # .del
    # Удаляет команду и последнее сохранённое своё сообщение
    # ------------------------------
    if command == "del":
        chat = await event.get_input_chat()
        ids = [event.id]

        if _last_own_message_id is not None:
            ids.append(_last_own_message_id)

        try:
            await bot.delete_messages(chat, list(set(ids)))
            _last_own_message_id = None
        except Exception as error:
            print(f"[CONTROL] Ошибка удаления: {error}")
            await event.edit("Не удалось удалить сообщение.")
        return

    # ------------------------------
    # .stopcontrol
    # Выключает только этот обработчик
    # ------------------------------
    if command == "stopcontrol":
        bot.remove_event_handler(control_commands_handler)
        try:
            await event.edit("Обработчик дополнительных команд выключен.")
        except Exception:
            pass
        return



#УДАЛЕНИЕ КОМАНД ЧТОБЫ НЕ ОПОЗОРИТЬСЯ


@bot.on(events.NewMessage)
async def delete_commands(event):

    if not event.raw_text:
        return

    text = event.raw_text.strip()

    for pattern in COMMAND_PATTERNS:

        if re.match(
            pattern,
            text,
            re.IGNORECASE
        ):

            try:

                await event.delete()

            except Exception as e:

                print(
                    f'Delete command error: {e}'
                )

            return


#ЗАГРУЗКА ШАБЛОНОВ


def load_phrases():

    phrases = []

    try:

        with open(
            PHRASES_FILE,
            'r',
            encoding='utf-8'
        ) as f:

            content = f.read()

        # Поддержка:
        # "фраза 1"
        # "фраза 2"

        matches = re.findall(
            r'"([^"]*)"',
            content
        )

        if matches:

            phrases = [
                phrase.strip()
                for phrase in matches
                if phrase.strip()
            ]

        else:

            # Обычный формат:
            # одна фраза = одна строка

            phrases = [
                line.strip()
                for line in content.splitlines()
                if line.strip()
            ]

        if not phrases:

            phrases = [
                'фраз не нашлось',
            ]

    except FileNotFoundError:

        print(
            f'Файл не найден: {PHRASES_FILE}'
        )

        phrases = [
            'фраз не нашлось',
        ]

    except Exception as e:

        print(
            f'Ошибка загрузки фраз: {e}'
        )

        phrases = [
            'фраз не нашлось',
        ]

    print(
        f'Загружено фраз: {len(phrases)}'
    )

    return phrases


REPLY_WORDS = load_phrases()


#ФОТО


def get_random_photo():

    valid_extensions = (
        '.jpg',
        '.jpeg',
        '.png',
        '.webp',
        '.gif'
    )

    try:

        files = os.listdir(
            PHOTOS_DIR
        )

        photos = [
            file
            for file in files
            if file.lower().endswith(
                valid_extensions
            )
        ]

        if photos:

            return os.path.join(
                PHOTOS_DIR,
                random.choice(photos)
            )

    except FileNotFoundError:

        print(
            f'Папка не найдена: {PHOTOS_DIR}'
        )

    except Exception as e:

        print(
            f'Ошибка загрузки фото: {e}'
        )

    return None


#РАМКА


FRAME_SYMBOLS = [
    '⛧',
    '†'
]


#РАНДОМ ШАБЛОН


def get_random_reply():

    if not REPLY_WORDS:

        return 'no phrases'

    reply = random.choice(
        REPLY_WORDS
    )

    symbol = random.choice(
        FRAME_SYMBOLS
    )

    return (
        f'{symbol} '
        f'{reply} '
        f'{symbol}'
    )


#ТЕГГЕР КОТОРЫЙ НЕ РАБОТАЕТ


async def tagger_task(
    chat_id,
    username,
    interval_seconds
):

    try:

        entity = await bot.get_entity(
            username
        )

    except Exception as e:

        print(
            f'Пользователь {username} не найден: {e}'
        )

        return

    if getattr(
        entity,
        'username',
        None
    ):

        mention = (
            f'@{entity.username}'
        )

    else:

        name = (
            getattr(
                entity,
                'first_name',
                None
            )
            or 'пользователь'
        )

        mention = (
            f'[{name}]'
            f'(tg://user?id={entity.id})'
        )

    while True:

        try:

            await asyncio.sleep(
                interval_seconds
            )

            await bot.send_message(
                chat_id,
                mention,
                parse_mode='md'
            )

            print(
                f'Tagged {mention} '
                f'in chat {chat_id}'
            )

        except asyncio.CancelledError:

            break

        except Exception as e:

            print(
                f'Tagger error: {e}'
            )

            break


#ТЕГГЕР КОТОРЫЙ НЕ РАБОТАЕТ


@bot.on(
    events.NewMessage(
        pattern=r'^\.tagger\s+(\S+)\s+(\d+)\s*(мин|минут|сек|секунд)?$'
    )
)
async def start_tagger(event):

    if event.sender_id != OWNER_ID:
        return

    chat_id = event.chat_id

    username = (
        event.pattern_match
        .group(1)
        .strip()
        .lstrip('@')
    )

    value = int(
        event.pattern_match
        .group(2)
    )

    unit = (
        event.pattern_match
        .group(3)
    )

    if unit:

        unit = unit.lower()

    else:

        # Если единица не указана,
        # считаем секунды

        unit = 'сек'

    if unit in (
        'мин',
        'минут'
    ):

        interval = value * 60

    else:

        interval = value

    # Минимум 5 секунд

    if interval < 5:

        print(
            'Tagger не запущен: '
            'минимальный интервал 5 секунд'
        )

        return

    # Если в этом чате уже есть теггер,
    # останавливаем его

    old_task = tag_tasks.get(
        chat_id
    )

    if old_task:

        old_task.cancel()

        try:

            await old_task

        except asyncio.CancelledError:

            pass

        except Exception:

            pass

        tag_tasks.pop(
            chat_id,
            None
        )

    # Запускаем новый

    task = asyncio.create_task(
        tagger_task(
            chat_id,
            username,
            interval
        )
    )

    tag_tasks[chat_id] = task

    print(
        f'Tagger запущен: '
        f'@{username}, '
        f'{value} {unit}, '
        f'chat={chat_id}'
    )


#.STOPTAGGER


@bot.on(
    events.NewMessage(
        pattern=r'^\.stoptagger$'
    )
)
async def stop_tagger(event):

    if event.sender_id != OWNER_ID:
        return

    chat_id = event.chat_id

    task = tag_tasks.get(
        chat_id
    )

    if task:

        task.cancel()

        try:

            await task

        except asyncio.CancelledError:

            pass

        except Exception:

            pass

        tag_tasks.pop(
            chat_id,
            None
        )

        print(
            f'Tagger stopped in chat {chat_id}'
        )

    else:

        print(
            f'No active tagger in chat {chat_id}'
        )


# ==========================================
# АВТОСООБЩЕНИЕ
# ==========================================


async def auto_message_task(
    chat_id,
    user_id,
    username,
    text
):

    try:

        while True:

            # Время ожидания в секундах
            # 1 = 1 секунда
            # 0.5 = 500 миллисекунд
            # 600 = 10 минут

            await asyncio.sleep(
                0.2
            )

            message = (
                f'<a href="tg://user?id={user_id}">'
                f'{html.escape(text)}'
                f'</a>'
            )

            await bot.send_message(
                chat_id,
                message,
                parse_mode='html'
            )

            print(
                f'Автосообщение отправлено '
                f'@{username} '
                f'в чат {chat_id}'
            )

    except asyncio.CancelledError:

        print(
            f'Auto остановлен: '
            f'@{username}'
        )

    except Exception as e:

        print(
            f'Auto error: {e}'
        )


# ==========================================
# .ADD ТЕКСТ @USERNAME
# ==========================================


@bot.on(
    events.NewMessage(
        outgoing=True,
        pattern=r"^\.add\s+@?([A-Za-z0-9_]{5,32})$"
    )
)
async def start_auto_message(event):
    if event.sender_id != OWNER_ID:
        return

    username = event.pattern_match.group(1).lower()
    chat_id = event.chat_id
    template = selected_templates.get(chat_id)

    if not template:
        await event.respond("Сначала выбери шаблон: .sb")
        return

    try:
        entity = await bot.get_entity(username)
        key = (chat_id, entity.id)

        add_templates[key] = template

        await event.respond(
            f"Автоответчик включён для @{username}.\n"
        )

    except Exception as error:
        print(f"[ADD] Ошибка: {error}")
        await event.respond("Не удалось найти пользователя.")


@bot.on(
    events.NewMessage(
        outgoing=True,
        pattern=r"^\.stopadd\s+@?([A-Za-z0-9_]{5,32})$"
    )
)
async def stop_auto_message(event):
    if event.sender_id != OWNER_ID:
        return

    username = event.pattern_match.group(1).lower()
    chat_id = event.chat_id

    try:
        entity = await bot.get_entity(username)
        key = (chat_id, entity.id)

        if add_templates.pop(key, None) is not None:
            await event.respond(f"Автоответчик для @{username} остановлен.")
        else:
            await event.respond(f"Для @{username} автоответчик не включён.")

    except Exception as error:
        print(f"[STOPADD] Ошибка: {error}")
        await event.respond("Не удалось найти пользователя.")


#АВТООТВЕТЧИК


@bot.on(events.NewMessage)
async def handler(event):
    if event.out:
        return

    chat_id = event.chat_id
    user_id = event.sender_id

    if chat_id is None or user_id is None:
        return

    key = (chat_id, user_id)

    is_add_target = key in add_templates
    is_regular_target = (
        chat_id in targets and user_id in targets[chat_id]
    )

    if not is_add_target and not is_regular_target:
        return

    if key in processing:
        return

    processing.add(key)

    try:
        await asyncio.sleep(0.2)

        reply = add_templates.get(key) or get_random_reply()
        photo = target_photos.get(user_id)

        if photo and os.path.exists(photo):
            await event.reply(reply, file=photo)
        else:
            await event.reply(reply)

    except Exception as e:
        print(f"Handler error: {e}")

    finally:
        processing.discard(key)



# .STARTRP


@bot.on(
    events.NewMessage(
        pattern=r'^\.startrp\s+(.+)$'
    )
)
async def add_target(event):

    if event.sender_id != OWNER_ID:
        return

    global targets

    chat_id = event.chat_id

    args = (
        event.pattern_match
        .group(1)
        .strip()
    )

    mentions = args.split()

    if not mentions:

        print(
            'Таргеты не указаны'
        )

        return

    if chat_id not in targets:

        targets[chat_id] = {}

    added = []
    not_found = []

    for mention in mentions:

        username = (
            mention
            .lstrip('@')
        )

        user_id = None

        # Можно указать ID напрямую

        if username.isdigit():

            user_id = int(
                username
            )

        else:

            try:

                entity = await bot.get_entity(
                    mention
                )

                user_id = entity.id

            except Exception:

                user_id = None

        if user_id:

            if user_id not in targets[chat_id]:

                targets[chat_id][user_id] = {
                    'username': mention
                }

                added.append(
                    mention
                )

            else:

                not_found.append(
                    f'{mention} (уже есть)'
                )

        else:

            not_found.append(
                mention
            )

    if added:

        print(
            f'Добавлены таргеты '
            f'в чате {chat_id}: '
            f'{", ".join(added)}'
        )

    if not_found:

        print(
            f'Не найдены/уже существуют '
            f'в чате {chat_id}: '
            f'{", ".join(not_found)}'
        )


# .UNRP


@bot.on(
    events.NewMessage(
        pattern=r'^\.unrp\s+(.+)$'
    )
)
async def remove_target(event):

    if event.sender_id != OWNER_ID:
        return

    global targets
    global processing

    chat_id = event.chat_id

    if chat_id not in targets:

        print(
            f'Нет активных таргетов '
            f'в чате {chat_id}'
        )

        return

    args = (
        event.pattern_match
        .group(1)
        .strip()
    )

    mentions = args.split()

    removed = []
    not_found = []

    for mention in mentions:

        username = (
            mention
            .lstrip('@')
        )

        user_id = None

        if username.isdigit():

            user_id = int(
                username
            )

        else:

            try:

                entity = await bot.get_entity(
                    mention
                )

                user_id = entity.id

            except Exception:

                user_id = None

        if (
            user_id
            and user_id in targets[chat_id]
        ):

            del targets[chat_id][user_id]

            removed.append(
                mention
            )

            processing.discard(
                (
                    chat_id,
                    user_id
                )
            )

        else:

            not_found.append(
                mention
            )

    # Если таргетов больше нет —
    # удаляем чат из словаря

    if not targets[chat_id]:

        del targets[chat_id]

    if removed:

        print(
            f'Удалены таргеты '
            f'в чате {chat_id}: '
            f'{", ".join(removed)}'
        )

    if not_found:

        print(
            f'Не найдены таргеты '
            f'в чате {chat_id}: '
            f'{", ".join(not_found)}'
        )


# .LIST

@bot.on(
    events.NewMessage(
        pattern=r'^\.list$'
    )
)
async def list_targets(event):

    if event.sender_id != OWNER_ID:
        return

    chat_id = event.chat_id

    if (
        chat_id not in targets
        or not targets[chat_id]
    ):
        await event.respond('⛧ ТАРГЕТОВ НЕ НАШЛОСЬ ⛧')
        return

    lines = [
        f'⛧ СПИСОК ТАРГЕТОВ ({len(targets[chat_id])}) ⛧',
        ''
    ]

    for user_id, data in targets[chat_id].items():

        username = data.get('username', str(user_id))

        if username.startswith('@'):
            display = username
        elif username.isdigit():
            display = f'ID: {username}'
        else:
            display = f'@{username}'

        lines.append(f'† {display} — {user_id}')

    message = '\n'.join(lines)

    await event.respond(message)


# .CLEAR RP


@bot.on(
    events.NewMessage(
        pattern=r'^\.clearrp$'
    )
)
async def clear_targets(event):

    if event.sender_id != OWNER_ID:
        return

    global targets

    chat_id = event.chat_id

    if chat_id in targets:

        count = len(
            targets[chat_id]
        )

        del targets[chat_id]

        print(
            f'Удалено таргетов: '
            f'{count} '
            f'в чате {chat_id}'
        )

    else:

        print(
            f'Нет активных таргетов '
            f'в чате {chat_id}'
        )


# .PHOTO


@bot.on(
    events.NewMessage(
        pattern=r'^\.photo\s+(\S+)\s+(.+)$'
    )
)
async def set_photo(event):

    if event.sender_id != OWNER_ID:
        return

    username = (
        event.pattern_match
        .group(1)
        .strip()
    )

    photo_name = (
        event.pattern_match
        .group(2)
        .strip()
    )

    try:

        entity = await bot.get_entity(
            username
        )

        user_id = entity.id

        photo_path = os.path.join(
            PHOTOS_DIR,
            photo_name
        )

        if not os.path.isfile(
            photo_path
        ):

            print(
                f'Фото не найдено: '
                f'{photo_path}'
            )

            return

        target_photos[user_id] = (
            photo_path
        )

        print(
            f'Фото установлено для '
            f'{username}: '
            f'{photo_path}'
        )

    except Exception as e:

        print(
            f'Photo error: {e}'
        )


# .ID


# .ID — ПОКАЗАТЬ ID ПОЛЬЗОВАТЕЛЯ В ЧАТЕ

@bot.on(
    events.NewMessage(
        pattern=r'^\.id$'
    )
)
async def get_id(event):

    if event.sender_id != OWNER_ID:
        return

    try:
        if event.is_reply:
            reply = await event.get_reply_message()

            if reply:
                user_id = reply.sender_id
            else:
                user_id = event.sender_id

        elif event.is_private:
            user_id = event.chat_id

        else:
            user_id = event.sender_id

        await event.respond(
            f'айди пользователя: {user_id}'
        )

    except Exception as e:
        print(f'ID error: {e}')


# .CHATID — ПОКАЗАТЬ ID ТЕКУЩЕГО ЧАТА

@bot.on(
    events.NewMessage(
        pattern=r'^\.chatid$'
    )
)
async def get_chat_id(event):

    if event.sender_id != OWNER_ID:
        return

    chat_id = event.chat_id

    await event.respond(
        f'айди чата: {chat_id}'
    )


# ПИКМИ — НАСТРОЙКИ


KAOMOJI = [
    '(灬ºωº灬)♡',
    '(≧◔◡◔≦)',
    '(´,,•ω•,,)♡',
    '(｡•̀ᴗ-)✧',
    '(๑>◡<๑)',
    '(〃ω〃)',
    '(｡･ω･｡)',
    '(≧▽≦)',
    '(♡˙︶˙♡)',
    '( ˶ˆ꒳ˆ˵ )'
]


SMALL_ELEMENTS = [
    '♡',
    '♥',
    '💓',
    '💗',
    '💞',
    '💖',
    '🥺',
    '✨',
    '🌸',
    '🎀'
]


WORDS = [
    'ня~',
    'ню~',
    'мяу~',
    'сенпай~'
]


ACTIONS = [
    '*молчит*',
    '*смущается*',
    '*отводит взгляд*',
    '*тихо смотрит*',
    '*прячется*',
    '*тихо улыбается*'
]


# ЗАИКАНИЕ


def stutter_word(word):

    if len(word) < 4:
        return word

    if word.startswith(
        (
            '@',
            '#',
            'http',
            'www.',
            'https://',
            'tg://'
        )
    ):

        return word

    match = re.match(
        r'^([А-Яа-яA-Za-zЁё]+)(.*)$',
        word
    )

    if not match:
        return word

    letters = match.group(1)
    ending = match.group(2)

    if random.random() < 0.55:

        first = letters[0]

        return (
            f'{first}-{letters}'
            f'{ending}'
        )

    count = random.choice(
        [2, 3]
    )

    if len(letters) <= count:
        return word

    prefix = letters[:count]

    return (
        f'{prefix}-{letters}'
        f'{ending}'
    )


def stutter_text(text):

    words = text.split()

    candidates = []

    for index, word in enumerate(words):

        clean = word.strip(
            '.,!?;:"\'()[]{}'
        )

        if len(clean) < 4:
            continue

        if clean.startswith(
            (
                '@',
                '#',
                'http',
                'www.'
            )
        ):

            continue

        candidates.append(
            index
        )

    if not candidates:
        return text

    count = 1

    if len(candidates) >= 3:

        if random.random() < 0.20:

            count = 2

    selected = random.sample(
        candidates,
        min(
            count,
            len(candidates)
        )
    )

    for index in selected:

        words[index] = stutter_word(
            words[index]
        )

    return ' '.join(words)


# МАЙКЕ ПИКМИ


def make_пикми(text):

    if not text:
        return text

    result = text

    result = stutter_text(
        result
    )

    result += ' ' + random.choice(
        KAOMOJI
    )

    result += ' ' + random.choice(
        SMALL_ELEMENTS
    )

    result += ' ' + random.choice(
        WORDS
    )

    result += ' ' + random.choice(
        ACTIONS
    )

    result += ' 👉👈'

    if len(result) > len(text) + 200:

        return text

    return result


# .PICKMEON


@bot.on(
    events.NewMessage(
        pattern=r'^\.pickmeon$'
    )
)
async def пикми_on(event):

    global пикми_enabled

    if event.sender_id != OWNER_ID:
        return

    пикми_enabled = True

    print(
        'пикми режим включён.'
    )


# .PICKMEOFF


@bot.on(
    events.NewMessage(
        pattern=r'^\.pickmeoff$'
    )
)
async def pickme_off(event):

    global пикми_enabled

    if event.sender_id != OWNER_ID:
        return

    пикми_enabled = False

    print(
        'пикми режим выключен.'
    )


# пикми


@bot.on(events.NewMessage)
async def пикми_editor(event):

    global пикми_enabled

    if not event.out:
        return

    if event.sender_id != OWNER_ID:
        return

    if not пикми_enabled:
        return

    text = event.raw_text.strip()

    if not text:
        return

    # Команды не редактируем

    if (
        text.startswith('.')
        or text.startswith('!')
    ):

        return

    # Ссылки не редактируем

    if (
        text.startswith('http://')
        or text.startswith('https://')
        or text.startswith('www.')
    ):

        return

    try:

        new_text = make_пикми(
            text
        )

        if not new_text:
            return

        if new_text == text:
            return

        await event.edit(
            new_text
        )

    except Exception as e:

        print(
            f'пикми editor error: {e}'
        )


# .MENU


@bot.on(
    events.NewMessage(
        pattern=r'^\.menu$'
    )
)
async def show_menu(event):

    if event.sender_id != OWNER_ID:
        return

    menu_text = """
⛧ lil menu ⛧

⛧ .startrp @user1 @user2  — добавить таргетов

⛧ .unrp @user1 @user2 — удалить таргетов

⛧ .list — список таргетов

⛧ .add текст @user — автосообщение

⛧ .stopadd @user — остановить автосообщение

⛧ .clearrp — удалить всех таргетов

⛧ .tagger @username 5 сек — запустить теггер

⛧ .stoptagger — остановить теггер

⛧ .photo @username photo.jpg — назначить фото

⛧ .id — показать айди

⛧ .pickmeon — включить пикми режим

⛧ .pickmeoff — выключить пикми режим

⛧ .menu — меню

⛧ .chatid - показывает айди чата

⛧ .sb — показать список шаблонов

⛧ .sb (номер шаблона) — выбрать шаблон

⛧ .sb reload — перечитать файл после редактирования

⛧ t.me/sertypa ⛧
"""
    
    await event.respond(menu_text)



# ЗАПУСК


async def main():

    print(
        'Запускается...'
    )

    await bot.start()

    print(
        'успешный запуск'
    )

    await bot.run_until_disconnected()


# START


if __name__ == '__main__':

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            '\nUserbot stopped'
        )
