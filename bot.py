import asyncio
import html
import random
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
)


# ============================================================
# НАСТРОЙКИ
# ============================================================

TOKEN = "8920982745:AAH5pu7gIIOpHq1UvrDrZMPNAY2KtLP81ZE"
ADMIN_ID = 295904020
DB_NAME = "design_challenge.db"

dp = Dispatcher()

user_states = {}
current_projects = {}
selected_projects = {}


# ============================================================
# БАЗА ДАННЫХ
# ============================================================

TABLE_NAMES = {
    "niches": "Ниши",
    "styles": "Стили",
    "associations": "Ассоциации",
}


DEFAULT_WELCOME = """Привет!

Это бот для дизайнерских челленджей — когда хочется потренироваться, поэкспериментировать или просто сделать что-нибудь интересное, но идеи испарились в неизвестном направлении.

Здесь можно случайным образом собрать задание из трёх элементов:

🎲 ниши
🎨 стиля
💭 ассоциаций

Можно собрать полноценный проект, взять только один элемент, заменить то, что не понравилось, сохранить идею и позже добавить ссылку на готовую работу.

Никаких оценок, дедлайнов и обязательств. Только ты, дизайн и иногда очень странные сочетания."""

DEFAULT_CREATOR = """👩‍💻 О создателе

Привет! Я Настя — веб-дизайнер с дипломом психолога.

Создала этого бота, потому что иногда дизайнеру хочется не срочно сделать очередной коммерческий экран, а просто потренироваться, поиграть с идеями и собрать что-нибудь неожиданное.

Здесь можно экспериментировать без брифа, правок, дедлайнов и фразы «а давайте сделаем посдержаннее».

🔗 Портфолио: добавь ссылку через админку
💬 Telegram: добавь ссылку через админку"""


def get_db():
    return sqlite3.connect(DB_NAME)


def init_db():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            niche TEXT,
            style TEXT,
            associations TEXT,
            link TEXT,
            status TEXT DEFAULT 'in_progress',
            published INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS niches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            active INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS styles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            active INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS associations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            active INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO settings (key, value)
        VALUES ('welcome', ?)
    """, (DEFAULT_WELCOME,))

    cursor.execute("""
        INSERT OR IGNORE INTO settings (key, value)
        VALUES ('creator', ?)
    """, (DEFAULT_CREATOR,))

    db.commit()
    db.close()


def get_setting(key, default=""):
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT value FROM settings WHERE key = ?",
        (key,)
    )

    result = cursor.fetchone()
    db.close()

    return result[0] if result else default


def save_setting(key, value):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key)
        DO UPDATE SET value = excluded.value
    """, (key, value))

    db.commit()
    db.close()


def save_user(message: Message):
    db = get_db()
    cursor = db.cursor()

    now = datetime.now().isoformat()

    cursor.execute("""
        INSERT OR IGNORE INTO users
        (telegram_id, username, created_at)
        VALUES (?, ?, ?)
    """, (
        message.from_user.id,
        message.from_user.username,
        now
    ))

    cursor.execute("""
        UPDATE users
        SET username = ?
        WHERE telegram_id = ?
    """, (
        message.from_user.username,
        message.from_user.id
    ))

    db.commit()
    db.close()


# ============================================================
# РАБОТА С ЭЛЕМЕНТАМИ
# ============================================================

def get_random_item(table_name):
    if table_name not in TABLE_NAMES:
        return None

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        f"""
        SELECT name
        FROM {table_name}
        WHERE active = 1
        ORDER BY RANDOM()
        LIMIT 1
        """
    )

    result = cursor.fetchone()
    db.close()

    return result[0] if result else None


def get_random_associations(count):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT name
        FROM associations
        WHERE active = 1
        ORDER BY RANDOM()
        LIMIT ?
    """, (count,))

    result = [
        row[0]
        for row in cursor.fetchall()
    ]

    db.close()

    return result


def get_items(table_name):
    if table_name not in TABLE_NAMES:
        return []

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        f"""
        SELECT id, name, active
        FROM {table_name}
        ORDER BY id
        """
    )

    result = cursor.fetchall()
    db.close()

    return result


def add_item(table_name, name):
    if table_name not in TABLE_NAMES:
        return False

    name = name.strip()

    if not name:
        return False

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            f"INSERT INTO {table_name} (name) VALUES (?)",
            (name,)
        )
        db.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False

    db.close()

    return success


def edit_item(table_name, item_id, new_name):
    if table_name not in TABLE_NAMES:
        return False

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            f"""
            UPDATE {table_name}
            SET name = ?
            WHERE id = ?
            """,
            (new_name.strip(), item_id)
        )

        success = cursor.rowcount > 0
        db.commit()

    except sqlite3.IntegrityError:
        success = False

    db.close()

    return success


def toggle_item(table_name, item_id):
    if table_name not in TABLE_NAMES:
        return False

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        f"""
        UPDATE {table_name}
        SET active = CASE
            WHEN active = 1 THEN 0
            ELSE 1
        END
        WHERE id = ?
        """,
        (item_id,)
    )

    success = cursor.rowcount > 0

    db.commit()
    db.close()

    return success


def delete_item(table_name, item_id):
    if table_name not in TABLE_NAMES:
        return False

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        f"""
        DELETE FROM {table_name}
        WHERE id = ?
        """,
        (item_id,)
    )

    success = cursor.rowcount > 0

    db.commit()
    db.close()

    return success


# ============================================================
# ПРОЕКТЫ
# ============================================================

def empty_project():
    return {
        "niche": None,
        "style": None,
        "associations": [],
        "link": None,
    }


def get_current_project(user_id):
    if user_id not in current_projects:
        current_projects[user_id] = empty_project()

    return current_projects[user_id]


def project_is_empty(project):
    return (
        not project["niche"]
        and not project["style"]
        and not project["associations"]
    )


def project_text(project):
    text = "🎯 <b>Текущий проект</b>\n\n"

    text += (
        f"🎲 Ниша: "
        f"<b>{html.escape(project['niche'])}</b>\n"
        if project["niche"]
        else "🎲 Ниша: —\n"
    )

    text += (
        f"🎨 Стиль: "
        f"<b>{html.escape(project['style'])}</b>\n"
        if project["style"]
        else "🎨 Стиль: —\n"
    )

    if project["associations"]:
        text += "\n💭 Ассоциации:\n"

        for association in project["associations"]:
            text += f"• {html.escape(association)}\n"
    else:
        text += "\n💭 Ассоциации: —\n"

    if project["link"]:
        text += (
            "\n🔗 Ссылка: "
            f"{html.escape(project['link'])}\n"
        )

    return text


def save_project_to_db(user_id, project):
    db = get_db()
    cursor = db.cursor()

    now = datetime.now().isoformat()

    associations = ", ".join(
        project["associations"]
    )

    cursor.execute("""
        INSERT INTO projects
        (
            telegram_id,
            niche,
            style,
            associations,
            link,
            status,
            published,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, 'in_progress', 0, ?, ?)
    """, (
        user_id,
        project["niche"],
        project["style"],
        associations,
        project["link"],
        now,
        now
    ))

    project_id = cursor.lastrowid

    db.commit()
    db.close()

    return project_id


def get_project(project_id, user_id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            id,
            niche,
            style,
            associations,
            link,
            status,
            published
        FROM projects
        WHERE id = ?
        AND telegram_id = ?
    """, (project_id, user_id))

    result = cursor.fetchone()
    db.close()

    return result


def update_project_link(project_id, user_id, link):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        UPDATE projects
        SET link = ?, updated_at = ?
        WHERE id = ?
        AND telegram_id = ?
    """, (
        link,
        datetime.now().isoformat(),
        project_id,
        user_id
    ))

    success = cursor.rowcount > 0

    db.commit()
    db.close()

    return success


def update_project_status(project_id, user_id, status):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        UPDATE projects
        SET status = ?, updated_at = ?
        WHERE id = ?
        AND telegram_id = ?
    """, (
        status,
        datetime.now().isoformat(),
        project_id,
        user_id
    ))

    success = cursor.rowcount > 0

    db.commit()
    db.close()

    return success


def publish_project_in_db(project_id, user_id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        UPDATE projects
        SET published = 1, updated_at = ?
        WHERE id = ?
        AND telegram_id = ?
        AND status = 'ready'
        AND link IS NOT NULL
        AND link != ''
    """, (
        datetime.now().isoformat(),
        project_id,
        user_id
    ))

    success = cursor.rowcount > 0

    db.commit()
    db.close()

    return success


# ============================================================
# КЛАВИАТУРЫ
# ============================================================

def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🎲 Ниша"),
                KeyboardButton(text="🎨 Стиль"),
            ],
            [
                KeyboardButton(text="💭 Ассоциации"),
            ],
            [
                KeyboardButton(text="🎯 Текущий проект"),
            ],
            [
                KeyboardButton(text="💾 Сохранить проект"),
                KeyboardButton(text="📁 Мои проекты"),
            ],
            [
                KeyboardButton(text="🌐 Галерея"),
                KeyboardButton(text="👩‍💻 О создателе"),
            ],
        ],
        resize_keyboard=True
    )


def project_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🎲 Заменить нишу"),
                KeyboardButton(text="🎨 Заменить стиль"),
            ],
            [
                KeyboardButton(text="💭 Добавить ассоциации"),
            ],
            [
                KeyboardButton(text="🔄 Заменить ассоциации"),
            ],
            [
                KeyboardButton(text="🔗 Добавить ссылку"),
            ],
            [
                KeyboardButton(text="💾 Сохранить проект"),
            ],
            [
                KeyboardButton(text="🆕 Новый проект"),
                KeyboardButton(text="◀️ Главное меню"),
            ],
        ],
        resize_keyboard=True
    )


def admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📝 Приветствие"),
                KeyboardButton(text="👩‍💻 О создателе"),
            ],
            [
                KeyboardButton(text="📣 Рассылка"),
            ],
            [
                KeyboardButton(text="➕ Ниши"),
                KeyboardButton(text="➕ Стили"),
            ],
            [
                KeyboardButton(text="➕ Ассоциации"),
            ],
            [
                KeyboardButton(text="📋 Ниши"),
                KeyboardButton(text="📋 Стили"),
            ],
            [
                KeyboardButton(text="📋 Ассоциации"),
            ],
            [
                KeyboardButton(text="📊 Статистика"),
            ],
            [
                KeyboardButton(text="◀️ Главное меню"),
            ],
        ],
        resize_keyboard=True
    )


def confirmation_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="✅ Подтвердить"),
                KeyboardButton(text="❌ Отмена"),
            ],
        ],
        resize_keyboard=True
    )


# ============================================================
# СТАРТ И ОБЩИЕ КНОПКИ
# ============================================================

@dp.message(CommandStart())
async def start(message: Message):
    save_user(message)
    user_states.pop(message.from_user.id, None)

    await message.answer(
        get_setting("welcome", DEFAULT_WELCOME),
        reply_markup=main_keyboard()
    )


@dp.message(
    lambda message:
    message.text == "👩‍💻 О создателе"
)
async def creator_info(message: Message):
    user_states.pop(message.from_user.id, None)

    await message.answer(
        get_setting("creator", DEFAULT_CREATOR),
        reply_markup=main_keyboard()
    )


@dp.message(
    lambda message:
    message.text == "◀️ Главное меню"
)
async def main_menu(message: Message):
    user_states.pop(message.from_user.id, None)

    await message.answer(
        "Главное меню:",
        reply_markup=main_keyboard()
    )


@dp.message(
    lambda message:
    message.text == "❌ Отмена"
)
async def cancel_action(message: Message):
    user_states.pop(message.from_user.id, None)

    await message.answer(
        "Отменила действие.",
        reply_markup=main_keyboard()
    )


# ============================================================
# ГЕНЕРАТОР
# ============================================================

@dp.message(lambda message: message.text == "🎲 Ниша")
async def random_niche(message: Message):
    user_states.pop(message.from_user.id, None)

    niche = get_random_item("niches")

    if not niche:
        await message.answer(
            "В базе пока нет активных ниш.\n\n"
            "Добавь их через /admin."
        )
        return

    project = get_current_project(
        message.from_user.id
    )

    project["niche"] = niche

    await message.answer(
        f"🎲 <b>Твоя ниша:</b>\n\n"
        f"{html.escape(niche)}\n\n"
        "Добавила её в текущий проект.",
        parse_mode="HTML",
        reply_markup=project_keyboard()
    )


@dp.message(lambda message: message.text == "🎨 Стиль")
async def random_style(message: Message):
    user_states.pop(message.from_user.id, None)

    style = get_random_item("styles")

    if not style:
        await message.answer(
            "В базе пока нет активных стилей.\n\n"
            "Добавь их через /admin."
        )
        return

    project = get_current_project(
        message.from_user.id
    )

    project["style"] = style

    await message.answer(
        f"🎨 <b>Твой стиль:</b>\n\n"
        f"{html.escape(style)}\n\n"
        "Добавила его в текущий проект.",
        parse_mode="HTML",
        reply_markup=project_keyboard()
    )


@dp.message(lambda message: message.text == "💭 Ассоциации")
async def random_associations(message: Message):
    user_states.pop(message.from_user.id, None)

    count = random.choice([2, 3, 4])
    associations = get_random_associations(count)

    if len(associations) < count:
        await message.answer(
            "В базе пока недостаточно активных ассоциаций."
        )
        return

    project = get_current_project(
        message.from_user.id
    )

    project["associations"] = associations

    text = "\n".join(
        f"• {html.escape(item)}"
        for item in associations
    )

    await message.answer(
        f"💭 <b>Твои ассоциации:</b>\n\n{text}\n\n"
        "Добавила их в текущий проект.",
        parse_mode="HTML",
        reply_markup=project_keyboard()
    )


@dp.message(lambda message: message.text == "🎲 Заменить нишу")
async def replace_niche(message: Message):
    niche = get_random_item("niches")

    if not niche:
        await message.answer(
            "В базе пока нет активных ниш."
        )
        return

    project = get_current_project(
        message.from_user.id
    )

    project["niche"] = niche

    await message.answer(
        f"🎲 <b>Новая ниша:</b>\n\n"
        f"{html.escape(niche)}",
        parse_mode="HTML",
        reply_markup=project_keyboard()
    )


@dp.message(lambda message: message.text == "🎨 Заменить стиль")
async def replace_style(message: Message):
    style = get_random_item("styles")

    if not style:
        await message.answer(
            "В базе пока нет активных стилей."
        )
        return

    project = get_current_project(
        message.from_user.id
    )

    project["style"] = style

    await message.answer(
        f"🎨 <b>Новый стиль:</b>\n\n"
        f"{html.escape(style)}",
        parse_mode="HTML",
        reply_markup=project_keyboard()
    )


@dp.message(
    lambda message:
    message.text == "💭 Добавить ассоциации"
)
async def add_associations(message: Message):
    count = random.choice([2, 3, 4])
    associations = get_random_associations(count)

    if len(associations) < count:
        await message.answer(
            "В базе пока недостаточно ассоциаций."
        )
        return

    project = get_current_project(
        message.from_user.id
    )

    added = []

    for item in associations:
        if item not in project["associations"]:
            project["associations"].append(item)
            added.append(item)

    if not added:
        await message.answer(
            "Выпали уже существующие ассоциации. "
            "Попробуй ещё раз.",
            reply_markup=project_keyboard()
        )
        return

    text = "\n".join(
        f"• {html.escape(item)}"
        for item in added
    )

    await message.answer(
        f"💭 <b>Добавила:</b>\n\n{text}",
        parse_mode="HTML",
        reply_markup=project_keyboard()
    )


@dp.message(
    lambda message:
    message.text == "🔄 Заменить ассоциации"
)
async def replace_associations(message: Message):
    count = random.choice([2, 3, 4])
    associations = get_random_associations(count)

    if len(associations) < count:
        await message.answer(
            "В базе пока недостаточно ассоциаций."
        )
        return

    project = get_current_project(
        message.from_user.id
    )

    project["associations"] = associations

    text = "\n".join(
        f"• {html.escape(item)}"
        for item in associations
    )

    await message.answer(
        f"🔄 <b>Новые ассоциации:</b>\n\n{text}",
        parse_mode="HTML",
        reply_markup=project_keyboard()
    )


@dp.message(
    lambda message:
    message.text == "🎯 Текущий проект"
)
async def show_current_project(message: Message):
    user_states.pop(message.from_user.id, None)

    project = get_current_project(
        message.from_user.id
    )

    if project_is_empty(project):
        await message.answer(
            "Пока здесь ничего нет.\n\n"
            "Выбери нишу, стиль или ассоциации.",
            reply_markup=project_keyboard()
        )
        return

    await message.answer(
        project_text(project),
        parse_mode="HTML",
        reply_markup=project_keyboard()
    )


@dp.message(
    lambda message:
    message.text == "🆕 Новый проект"
)
async def new_project(message: Message):
    current_projects[
        message.from_user.id
    ] = empty_project()

    user_states.pop(message.from_user.id, None)

    await message.answer(
        "🆕 Создала новый пустой проект.",
        reply_markup=project_keyboard()
    )


# ============================================================
# ССЫЛКИ И СОХРАНЕНИЕ
# ============================================================

@dp.message(
    lambda message:
    message.text == "🔗 Добавить ссылку"
)
async def ask_link(message: Message):
    user_states[message.from_user.id] = {
        "action": "current_link"
    }

    await message.answer(
        "Пришли ссылку на готовую работу.\n\n"
        "Она должна начинаться с http:// или https://",
        reply_markup=confirmation_keyboard()
    )


@dp.message(
    lambda message:
    message.text == "💾 Сохранить проект"
)
async def save_current_project(message: Message):
    user_states.pop(message.from_user.id, None)

    project = get_current_project(
        message.from_user.id
    )

    if project_is_empty(project):
        await message.answer(
            "Проект пока пустой. "
            "Добавь хотя бы один элемент."
        )
        return

    project_id = save_project_to_db(
        message.from_user.id,
        project
    )

    current_projects.pop(
        message.from_user.id,
        None
    )

    await message.answer(
        f"💾 <b>Проект #{project_id} сохранён.</b>\n\n"
        "Статус: в процессе.\n"
        "Позже можно будет добавить ссылку, "
        "отметить проект готовым и опубликовать его.",
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )


# ============================================================
# МОИ ПРОЕКТЫ
# ============================================================

@dp.message(
    lambda message:
    message.text == "📁 Мои проекты"
)
async def my_projects(message: Message):
    user_states.pop(message.from_user.id, None)

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            id,
            niche,
            style,
            associations,
            link,
            status,
            published
        FROM projects
        WHERE telegram_id = ?
        ORDER BY id DESC
    """, (message.from_user.id,))

    projects = cursor.fetchall()
    db.close()

    if not projects:
        await message.answer(
            "Здесь пока пусто.\n\n"
            "Сохраняй собранные идеи, чтобы "
            "возвращаться к ним позже.",
            reply_markup=main_keyboard()
        )
        return

    text = "📁 <b>Мои проекты</b>\n\n"

    for project in projects:
        (
            project_id,
            niche,
            style,
            associations,
            link,
            status,
            published
        ) = project

        status_text = (
            "готов"
            if status == "ready"
            else "в процессе"
        )

        text += f"<b>Проект #{project_id}</b>\n"

        if niche:
            text += f"🎲 Ниша: {html.escape(niche)}\n"

        if style:
            text += f"🎨 Стиль: {html.escape(style)}\n"

        if associations:
            text += (
                f"💭 Ассоциации: "
                f"{html.escape(associations)}\n"
            )

        if link:
            text += f"🔗 {html.escape(link)}\n"

        text += f"Статус: {status_text}\n"

        if published:
            text += "🌐 Опубликован в галерее\n"

        text += "\n"

    text += (
        "Чтобы управлять проектом, напиши:\n"
        "<code>проект ID</code>"
    )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )


@dp.message(
    lambda message:
    message.text.startswith("проект ")
)
async def select_project(message: Message):
    try:
        project_id = int(
            message.text.split()[1]
        )
    except (ValueError, IndexError):
        await message.answer(
            "Напиши, например: проект 3"
        )
        return

    project = get_project(
        project_id,
        message.from_user.id
    )

    if not project:
        await message.answer(
            "Не нашла такой проект."
        )
        return

    selected_projects[
        message.from_user.id
    ] = project_id

    (
        project_id,
        niche,
        style,
        associations,
        link,
        status,
        published
    ) = project

    text = f"<b>Проект #{project_id}</b>\n\n"

    if niche:
        text += f"🎲 Ниша: {html.escape(niche)}\n"

    if style:
        text += f"🎨 Стиль: {html.escape(style)}\n"

    if associations:
        text += (
            f"💭 Ассоциации: "
            f"{html.escape(associations)}\n"
        )

    if link:
        text += f"🔗 {html.escape(link)}\n"

    text += (
        "\nСтатус: "
        + ("готов" if status == "ready" else "в процессе")
    )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="🔗 Добавить ссылку к проекту"),
                ],
                [
                    KeyboardButton(text="✅ Отметить готовым"),
                ],
                [
                    KeyboardButton(text="🌐 Опубликовать проект"),
                ],
                [
                    KeyboardButton(text="◀️ Главное меню"),
                ],
            ],
            resize_keyboard=True
        )
    )


@dp.message(
    lambda message:
    message.text == "🔗 Добавить ссылку к проекту"
)
async def add_link_to_saved_project(message: Message):
    if message.from_user.id not in selected_projects:
        await message.answer(
            "Сначала выбери проект командой:\n"
            "проект ID"
        )
        return

    user_states[message.from_user.id] = {
        "action": "saved_link",
        "project_id": selected_projects[
            message.from_user.id
        ]
    }

    await message.answer(
        "Пришли ссылку на готовую работу.",
        reply_markup=confirmation_keyboard()
    )


@dp.message(
    lambda message:
    message.text == "✅ Отметить готовым"
)
async def mark_project_ready(message: Message):
    project_id = selected_projects.get(
        message.from_user.id
    )

    if not project_id:
        await message.answer(
            "Сначала выбери проект командой:\n"
            "проект ID"
        )
        return

    success = update_project_status(
        project_id,
        message.from_user.id,
        "ready"
    )

    await message.answer(
        "✅ Проект отмечен как готовый."
        if success
        else "Не удалось изменить статус.",
        reply_markup=main_keyboard()
    )


@dp.message(
    lambda message:
    message.text == "🌐 Опубликовать проект"
)
async def publish_selected_project(message: Message):
    project_id = selected_projects.get(
        message.from_user.id
    )

    if not project_id:
        await message.answer(
            "Сначала выбери проект командой:\n"
            "проект ID"
        )
        return

    success = publish_project_in_db(
        project_id,
        message.from_user.id
    )

    if success:
        text = (
            "🌐 Проект опубликован в галерее.\n\n"
            "Его смогут увидеть другие участники."
        )
    else:
        text = (
            "Не получилось опубликовать проект.\n\n"
            "Проверь, что он отмечен как готовый "
            "и у него есть ссылка."
        )

    await message.answer(
        text,
        reply_markup=main_keyboard()
    )


# ============================================================
# ГАЛЕРЕЯ
# ============================================================

@dp.message(
    lambda message:
    message.text == "🌐 Галерея"
)
async def gallery(message: Message):
    user_states.pop(message.from_user.id, None)

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            id,
            niche,
            style,
            associations,
            link
        FROM projects
        WHERE status = 'ready'
        AND published = 1
        AND link IS NOT NULL
        AND link != ''
        ORDER BY id DESC
        LIMIT 50
    """)

    projects = cursor.fetchall()
    db.close()

    if not projects:
        await message.answer(
            "Галерея пока пустая.\n\n"
            "Будь первой, кто добавит сюда готовую работу.",
            reply_markup=main_keyboard()
        )
        return

    text = "🌐 <b>Галерея работ</b>\n\n"

    for project in projects:
        (
            project_id,
            niche,
            style,
            associations,
            link
        ) = project

        text += f"<b>Проект #{project_id}</b>\n"

        if niche:
            text += f"🎲 Ниша: {html.escape(niche)}\n"

        if style:
            text += f"🎨 Стиль: {html.escape(style)}\n"

        if associations:
            text += (
                f"💭 Ассоциации: "
                f"{html.escape(associations)}\n"
            )

        text += f"🔗 {html.escape(link)}\n\n"

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )


# ============================================================
# АДМИНКА
# ============================================================

def is_admin(message: Message):
    return message.from_user.id == ADMIN_ID


@dp.message(
    lambda message:
    message.text == "/admin"
    and is_admin(message)
)
async def admin_start(message: Message):
    user_states.pop(message.from_user.id, None)

    await message.answer(
        "🔐 <b>Админка</b>\n\n"
        "Здесь можно управлять содержимым бота.",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


@dp.message(
    lambda message:
    message.text == "/admin"
    and not is_admin(message)
)
async def admin_denied(message: Message):
    await message.answer(
        "У тебя нет доступа к админке."
    )


@dp.message(
    lambda message:
    message.text == "📝 Приветствие"
    and is_admin(message)
)
async def edit_welcome_start(message: Message):
    user_states[message.from_user.id] = {
        "action": "edit_setting",
        "setting": "welcome"
    }

    await message.answer(
        "📝 <b>Текущее приветствие:</b>\n\n"
        f"{html.escape(get_setting('welcome'))}\n\n"
        "Пришли новый текст одним сообщением.",
        parse_mode="HTML",
        reply_markup=confirmation_keyboard()
    )


@dp.message(
    lambda message:
    message.text == "👩‍💻 О создателе"
    and is_admin(message)
)
async def edit_creator_start(message: Message):
    user_states[message.from_user.id] = {
        "action": "edit_setting",
        "setting": "creator"
    }

    await message.answer(
        "👩‍💻 <b>Текущая информация о создателе:</b>\n\n"
        f"{html.escape(get_setting('creator'))}\n\n"
        "Пришли новый текст одним сообщением.",
        parse_mode="HTML",
        reply_markup=confirmation_keyboard()
    )


@dp.message(
    lambda message:
    message.text == "📣 Рассылка"
    and is_admin(message)
)
async def mailing_start(message: Message):
    user_states[message.from_user.id] = {
        "action": "mailing_text"
    }

    await message.answer(
        "📣 <b>Рассылка</b>\n\n"
        "Пришли текст сообщения, которое нужно "
        "отправить всем пользователям бота.\n\n"
        "Перед отправкой я покажу предпросмотр.",
        parse_mode="HTML",
        reply_markup=confirmation_keyboard()
    )


@dp.message(
    lambda message:
    message.text == "➕ Ниши"
    and is_admin(message)
)
async def admin_add_niches(message: Message):
    user_states[message.from_user.id] = {
        "action": "add_items",
        "table": "niches"
    }

    await message.answer(
        "Пришли одну или несколько ниш.\n"
        "Каждая — с новой строки.",
        reply_markup=confirmation_keyboard()
    )


@dp.message(
    lambda message:
    message.text == "➕ Стили"
    and is_admin(message)
)
async def admin_add_styles(message: Message):
    user_states[message.from_user.id] = {
        "action": "add_items",
        "table": "styles"
    }

    await message.answer(
        "Пришли один или несколько стилей.\n"
        "Каждый — с новой строки.",
        reply_markup=confirmation_keyboard()
    )


@dp.message(
    lambda message:
    message.text == "➕ Ассоциации"
    and is_admin(message)
)
async def admin_add_associations(message: Message):
    user_states[message.from_user.id] = {
        "action": "add_items",
        "table": "associations"
    }

    await message.answer(
        "Пришли одну или несколько ассоциаций.\n"
        "Каждая — с новой строки.",
        reply_markup=confirmation_keyboard()
    )


async def show_admin_list(message: Message, table_name):
    items = get_items(table_name)

    if not items:
        await message.answer(
            f"{TABLE_NAMES[table_name]} пока пусты."
        )
        return

    text = (
        f"📋 <b>{TABLE_NAMES[table_name]}</b>\n\n"
    )

    for item_id, name, active in items:
        status = "🟢" if active else "🔴"

        text += (
            f"{status} <b>{item_id}</b> — "
            f"{html.escape(name)}\n"
        )

    text += """

Команды:

изменить ID Новый текст

удалить ID

переключить ID
"""

    await message.answer(
        text,
        parse_mode="HTML"
    )


@dp.message(
    lambda message:
    message.text == "📋 Ниши"
    and is_admin(message)
)
async def admin_list_niches(message: Message):
    user_states[message.from_user.id] = {
        "action": "manage",
        "table": "niches"
    }

    await show_admin_list(message, "niches")


@dp.message(
    lambda message:
    message.text == "📋 Стили"
    and is_admin(message)
)
async def admin_list_styles(message: Message):
    user_states[message.from_user.id] = {
        "action": "manage",
        "table": "styles"
    }

    await show_admin_list(message, "styles")


@dp.message(
    lambda message:
    message.text == "📋 Ассоциации"
    and is_admin(message)
)
async def admin_list_associations(message: Message):
    user_states[message.from_user.id] = {
        "action": "manage",
        "table": "associations"
    }

    await show_admin_list(message, "associations")


@dp.message(
    lambda message:
    message.text == "📊 Статистика"
    and is_admin(message)
)
async def admin_stats(message: Message):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM projects")
    projects = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM projects WHERE status = 'ready'"
    )
    ready_projects = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM projects WHERE published = 1"
    )
    published = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM niches")
    niches = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM styles")
    styles = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM associations")
    associations = cursor.fetchone()[0]

    db.close()

    await message.answer(
        "📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: {users}\n"
        f"🎯 Проектов: {projects}\n"
        f"✅ Готовых проектов: {ready_projects}\n"
        f"🌐 Опубликовано: {published}\n\n"
        f"🎲 Ниш: {niches}\n"
        f"🎨 Стилей: {styles}\n"
        f"💭 Ассоциаций: {associations}",
        parse_mode="HTML"
    )


# ============================================================
# ОБРАБОТКА СОСТОЯНИЙ
# ============================================================

async def send_mailing(bot: Bot, text: str):
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT telegram_id FROM users"
    )

    user_ids = [
        row[0]
        for row in cursor.fetchall()
    ]

    db.close()

    success = 0
    failed = 0

    for user_id in user_ids:
        try:
            await bot.send_message(
                user_id,
                text
            )
            success += 1

        except Exception:
            failed += 1

        await asyncio.sleep(0.05)

    return success, failed, len(user_ids)


@dp.message()
async def state_handler(message: Message):
    user_id = message.from_user.id
    state = user_states.get(user_id)

    if not state:
        return

    action = state.get("action")

    # --------------------------------------------------------
    # РЕДАКТИРОВАНИЕ НАСТРОЕК
    # --------------------------------------------------------

    if action == "edit_setting":
        if message.text == "❌ Отмена":
            user_states.pop(user_id, None)

            await message.answer(
                "Изменение отменено.",
                reply_markup=admin_keyboard()
            )
            return

        setting = state["setting"]

        save_setting(
            setting,
            message.text
        )

        user_states.pop(user_id, None)

        await message.answer(
            "✅ Настройка обновлена.",
            reply_markup=admin_keyboard()
        )

        return

    # --------------------------------------------------------
    # ДОБАВЛЕНИЕ ЭЛЕМЕНТОВ
    # --------------------------------------------------------

    if action == "add_items":
        if message.text == "❌ Отмена":
            user_states.pop(user_id, None)

            await message.answer(
                "Добавление отменено.",
                reply_markup=admin_keyboard()
            )
            return

        table_name = state["table"]

        lines = [
            line.strip()
            for line in message.text.splitlines()
            if line.strip()
        ]

        added = 0
        duplicates = 0

        for line in lines:
            if add_item(table_name, line):
                added += 1
            else:
                duplicates += 1

        user_states.pop(user_id, None)

        await message.answer(
            "✅ Готово.\n\n"
            f"Добавлено: {added}\n"
            f"Дубликатов: {duplicates}",
            reply_markup=admin_keyboard()
        )

        return

    # --------------------------------------------------------
    # ТЕКУЩИЙ ПРОЕКТ — ССЫЛКА
    # --------------------------------------------------------

    if action == "current_link":
        if message.text == "❌ Отмена":
            user_states.pop(user_id, None)

            await message.answer(
                "Добавление ссылки отменено.",
                reply_markup=project_keyboard()
            )
            return

        link = message.text.strip()

        if not (
            link.startswith("http://")
            or link.startswith("https://")
        ):
            await message.answer(
                "Пришли ссылку, которая начинается "
                "с http:// или https://"
            )
            return

        project = get_current_project(user_id)
        project["link"] = link

        user_states.pop(user_id, None)

        await message.answer(
            "🔗 Ссылка добавлена.\n\n"
            + project_text(project),
            parse_mode="HTML",
            reply_markup=project_keyboard()
        )

        return

    # --------------------------------------------------------
    # СОХРАНЁННЫЙ ПРОЕКТ — ССЫЛКА
    # --------------------------------------------------------

    if action == "saved_link":
        if message.text == "❌ Отмена":
            user_states.pop(user_id, None)

            await message.answer(
                "Добавление ссылки отменено.",
                reply_markup=main_keyboard()
            )
            return

        link = message.text.strip()

        if not (
            link.startswith("http://")
            or link.startswith("https://")
        ):
            await message.answer(
                "Пришли ссылку, которая начинается "
                "с http:// или https://"
            )
            return

        project_id = state["project_id"]

        success = update_project_link(
            project_id,
            user_id,
            link
        )

        user_states.pop(user_id, None)

        await message.answer(
            "🔗 Ссылка добавлена к проекту."
            if success
            else "Не удалось добавить ссылку.",
            reply_markup=main_keyboard()
        )

        return

    # --------------------------------------------------------
    # РАССЫЛКА — ТЕКСТ
    # --------------------------------------------------------

    if action == "mailing_text":
        if message.text == "❌ Отмена":
            user_states.pop(user_id, None)

            await message.answer(
                "Рассылка отменена.",
                reply_markup=admin_keyboard()
            )
            return

        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM users"
        )

        count = cursor.fetchone()[0]
        db.close()

        user_states[user_id] = {
            "action": "mailing_confirm",
            "text": message.text
        }

        await message.answer(
            "📣 <b>Предпросмотр рассылки</b>\n\n"
            f"{html.escape(message.text)}\n\n"
            f"Получателей: {count}\n\n"
            "Отправить это сообщение всем участникам?",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [
                        KeyboardButton(text="✅ Отправить"),
                        KeyboardButton(text="❌ Отмена"),
                    ]
                ],
                resize_keyboard=True
            )
        )

        return

    # --------------------------------------------------------
    # РАССЫЛКА — ПОДТВЕРЖДЕНИЕ
    # --------------------------------------------------------

    if action == "mailing_confirm":
        if message.text == "❌ Отмена":
            user_states.pop(user_id, None)

            await message.answer(
                "Рассылку отменила. Ничего не отправлено.",
                reply_markup=admin_keyboard()
            )
            return

        if message.text != "✅ Отправить":
            await message.answer(
                "Нажми «✅ Отправить» или «❌ Отмена»."
            )
            return

        mailing_text = state["text"]

        user_states.pop(user_id, None)

        await message.answer(
            "📣 Начинаю рассылку. Это может занять некоторое время."
        )

        bot = message.bot

        success, failed, total = await send_mailing(
            bot,
            mailing_text
        )

        await message.answer(
            "📊 <b>Рассылка завершена</b>\n\n"
            f"Успешно отправлено: {success}\n"
            f"Не доставлено: {failed}\n"
            f"Всего получателей: {total}",
            parse_mode="HTML",
            reply_markup=admin_keyboard()
        )

        return

    # --------------------------------------------------------
    # УПРАВЛЕНИЕ СПИСКАМИ
    # --------------------------------------------------------

    if action == "manage":
        if message.text == "❌ Отмена":
            user_states.pop(user_id, None)

            await message.answer(
                "Действие отменено.",
                reply_markup=admin_keyboard()
            )
            return

        parts = message.text.strip().split(
            maxsplit=2
        )

        command = parts[0].lower()
        table_name = state["table"]

        if command == "удалить":
            if len(parts) != 2:
                await message.answer(
                    "Формат: удалить ID"
                )
                return

            try:
                item_id = int(parts[1])
            except ValueError:
                await message.answer(
                    "ID должен быть числом."
                )
                return

            success = delete_item(
                table_name,
                item_id
            )

            await message.answer(
                "🗑 Удалено."
                if success
                else "Такого ID нет."
            )

            return

        if command == "переключить":
            if len(parts) != 2:
                await message.answer(
                    "Формат: переключить ID"
                )
                return

            try:
                item_id = int(parts[1])
            except ValueError:
                await message.answer(
                    "ID должен быть числом."
                )
                return

            success = toggle_item(
                table_name,
                item_id
            )

            await message.answer(
                "🔄 Статус изменён."
                if success
                else "Такого ID нет."
            )

            return

        if command == "изменить":
            if len(parts) != 3:
                await message.answer(
                    "Формат: изменить ID Новый текст"
                )
                return

            try:
                item_id = int(parts[1])
            except ValueError:
                await message.answer(
                    "ID должен быть числом."
                )
                return

            success = edit_item(
                table_name,
                item_id,
                parts[2]
            )

            await message.answer(
                "✏️ Изменено."
                if success
                else "Не удалось изменить."
            )

            return

        await message.answer(
            "Не поняла команду.\n\n"
            "Доступно:\n"
            "удалить ID\n"
            "переключить ID\n"
            "изменить ID Новый текст"
        )


# ============================================================
# ЗАПУСК
# ============================================================

async def main():
    init_db()

    bot = Bot(token=TOKEN)

    print("Бот запущен.")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())