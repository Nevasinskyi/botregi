import asyncio
import html
import random
import os
import time
import re
import psutil
from config import API_ID, API_HASH, COMMAND_PATTERNS, OWNER_ID, BASE_DIR, PHRASES_FILE
from dotenv import load_dotenv
from telethon.sessions import StringSession
from telethon import TelegramClient, events
from pathlib import Path

#ВХОД ПО СЕССИИ
import os
from telethon.sessions import StringSession

session_string = os.environ.get("TELEGRAM_SESSION", "").strip()

if not session_string:
    raise RuntimeError("Не задана переменная TELEGRAM_SESSION")

bot = TelegramClient(
    StringSession(session_string),
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

selected_template = {}

пикми_enabled = True
пикми_enabled = False

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

# Автоответчики: (chat_id, user_id) -> текст шаблона
add_templates = {}

# ==========================================
# АВТОСООБЩЕНИЕ
# ==========================================

auto_tasks = {}


async def auto_message_task(
    chat_id,
    user_id,
    username,
    text
):
    try:

        while True:

            await asyncio.sleep(100 / 1000)

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
                f'@{username} в чат {chat_id}'
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
        pattern=r'^\.add\s+(.+)\s+@([A-Za-z0-9_]{5,32})$'
    )
)
async def start_auto_message(event):

    if event.sender_id != OWNER_ID:
        return

    text = (
        event.pattern_match
        .group(1)
        .strip()
    )

    username = (
        event.pattern_match
        .group(2)
        .strip()
        .lower()
    )

    chat_id = event.chat_id

    key = (
        chat_id,
        username
    )

    try:

        entity = await bot.get_entity(
            username
        )

        user_id = entity.id

        # Если уже есть Auto —
        # сначала останавливаем его

        old_task = auto_tasks.get(
            key
        )

        if old_task:

            old_task.cancel()

            try:
                await old_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

            auto_tasks.pop(
                key,
                None
            )

        # Создаём новую задачу

        task = asyncio.create_task(
            auto_message_task(
                chat_id,
                user_id,
                username,
                text
            )
        )

        auto_tasks[key] = task

        print(
            f'Auto запущен: '
            f'@{username}, '
            f'chat={chat_id}'
        )

    except Exception as e:

        print(
            f'Ошибка запуска Auto: {e}'
        )


# ==========================================
# .STOPADD @USERNAME
# ==========================================

@bot.on(
    events.NewMessage(
        pattern=r'^\.stopadd\s+@?([A-Za-z0-9_]{5,32})$'
    )
)
async def stop_auto_message(event):

    if event.sender_id != OWNER_ID:
        return

    username = (
        event.pattern_match
        .group(1)
        .strip()
        .lower()
    )

    chat_id = event.chat_id

    key = (
        chat_id,
        username
    )

    print(
        f'Остановка Auto: '
        f'@{username}, '
        f'chat={chat_id}'
    )

    task = auto_tasks.pop(
        key,
        None
    )

    if task:

        task.cancel()

        print(
            f'Auto успешно остановлен: '
            f'@{username}'
        )

    else:

        print(
            f'Auto не найден: '
            f'@{username} '
            f'в чате {chat_id}'
        )
 
# ==============================
# СОСТОЯНИЕ ПРОЦЕССА БОТА
# ==============================

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
⛧ yocio menu ⛧

⛧ .startrp @user1 @user2  — добавить таргетов
⛧ .unrp @user1 @user2 — удалить таргетов
⛧ .list — список таргетов
⛧ .clearrp — удалить всех таргетов
⛧ .tagger @username 5 сек — запустить теггер
⛧ .stoptagger — остановить теггер
⛧ .photo @username photo.jpg — назначить фото
⛧ .id — показать айди
⛧ .add @user — спам текстом
⛧ .stopadd — останавливает
⛧ .pickmeon — включить пикми режим
⛧ .pickmeoff — выключить пикми режим
⛧ .menu — меню
⛧ .chatid — показывает айди чата

⛧ owner t.me/sertypa ⛧
"""
    
    await event.respond(menu_text)



# ЗАПУСК


async def main():
    print('Запускается...')

    await bot.connect()

    if not await bot.is_user_authorized():
        raise RuntimeError(
            "Сессия не авторизована. Проверь TELEGRAM_SESSION в Railway."
        )

    print('Успешный запуск')

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
