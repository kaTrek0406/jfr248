import asyncio
import os
import sqlite3
from datetime import datetime, timedelta, date

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest

# ================== НАСТРОЙКИ ==================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8469639824:AAGv98XLctt4O3lP9C4VLONEyi-fqeNQxRc").strip()
DB_PATH   = os.getenv("DB_PATH", "./schedule.db")

GROUP       = "JFR-237"
GROUP_LABEL = "Jurnalism și procese mediatice — JFR-237"

# Фиксированный UTC+3 без танцев с tzdata (Windows/railway-safe)
TZ_OFFSET_HOURS = 3

# Небольшая проверка токена (поможет, если промахнуться в Railway Variables)
import re, sys
TOKEN_RE = re.compile(r"^\d{5,12}:[A-Za-z0-9_-]{20,}$")
if not TOKEN_RE.match(BOT_TOKEN or ""):
    print("[FATAL] Укажи BOT_TOKEN (токен бота от @BotFather) в переменных окружения.")
    sys.exit(1)

# ================== РАСПИСАНИЕ (ВШИТО) ==================
# Формат: (YYYY-MM-DD, HH:MM, HH:MM, Title, Teacher, Room)
SCHEDULE: list[tuple[str,str,str,str,str,str]] = [
    # 22.09.2025 (luni)
    ("2025-09-22","15:00","16:30","Etică și integritate profesională","Asistent universitar A. Mărgineanu","s. 427"),
    ("2025-09-22","16:45","18:15","Etică și integritate profesională","Asistent universitar A. Mărgineanu","s. 427"),

    # 23.09.2025 (marți)
    ("2025-09-23","13:15","14:45","Jurnalism radio","Asistent universitar V. Cernea","432/407/Bl. Central"),
    ("2025-09-23","15:00","16:30","Jurnalism radio","Asistent universitar V. Cernea","432/407/Bl. Central"),

    # 24.09.2025 (miercuri)
    ("2025-09-24","13:15","14:45","Etică și integritate profesională","Asistent universitar A. Mărgineanu","s. 432"),
    ("2025-09-24","15:00","16:30","Etică și integritate profesională","Asistent universitar A. Mărgineanu","s. 432"),

    # 25.09.2025 (joi)
    ("2025-09-25","13:15","14:45","Știrea","Dr., conf. univ. M. Tacu","s. 432"),
    ("2025-09-25","15:00","16:30","Știrea","Dr., conf. univ. M. Tacu","s. 432"),

    # 26.09.2025 (vineri)
    ("2025-09-26","15:00","16:30","Jurnalism radio","Asistent universitar V. Cernea","407/Bl. Central"),
    ("2025-09-26","16:45","18:15","Jurnalism radio","Asistent universitar V. Cernea","407/Bl. Central"),
    ("2025-09-26","18:30","20:00","Disciplina U","Dr., conf. univ. A. Colațchi","Blocul 2/ s. 102"),
    ("2025-09-26","20:15","21:45","Disciplina U","Dr., conf. univ. A. Colațchi","Blocul 2/ s. 102"),

    # 27.09.2025 (sâmbătă)
    ("2025-09-27","08:00","09:30","Disciplina U","Dr., conf. univ. A. Colațchi","Blocul 2/ s. 102"),
    ("2025-09-27","09:45","11:15","Disciplina U","Dr., conf. univ. A. Colațchi","Blocul 2/ s. 102"),
    ("2025-09-27","11:30","13:00","Jurnalism radio","Asistent universitar V. Cernea","429/407/Bl. Central"),
    ("2025-09-27","13:15","14:45","Jurnalism radio","Asistent universitar V. Cernea","429/407/Bl. Central"),

    # 29.09.2025 (luni)
    ("2025-09-29","15:00","16:30","Jurnalism radio","Asistent universitar V. Cernea","429/407/Bl. Central"),
    ("2025-09-29","16:45","18:15","Jurnalism radio","Asistent universitar V. Cernea","429/407/Bl. Central"),

    # 30.09.2025 (marți)
    ("2025-09-30","13:15","14:45","Etică și integritate profesională","Asistent universitar A. Mărgineanu","s. 427"),
    ("2025-09-30","15:00","16:30","Etică și integritate profesională","Asistent universitar A. Mărgineanu","s. 427"),

    # 01.10.2025 (miercuri)
    ("2025-10-01","15:00","16:30","Jurnalism radio","Asistent universitar V. Cernea","429/407/Bl. Central"),
    ("2025-10-01","16:45","18:15","Jurnalism radio","Asistent universitar V. Cernea","429/407/Bl. Central"),
    ("2025-10-01","18:30","20:00","Disciplina U","Dr., conf. univ. A. Colațchi","Blocul 2/ s. 102"),
    ("2025-10-01","20:15","21:45","Disciplina U","Dr., conf. univ. A. Colațchi","Blocul 2/ s. 102"),

    # 02.10.2025 (joi)
    ("2025-10-02","13:15","14:45","Știrea","Dr., conf. univ. M. Tacu","s. 432"),
    ("2025-10-02","15:00","16:30","Știrea","Dr., conf. univ. M. Tacu","s. 432"),

    # 03.10.2025 (vineri)
    ("2025-10-03","15:00","16:30","Jurnalism radio","Asistent universitar V. Cernea","429/407/Bl. Central"),
    ("2025-10-03","16:45","18:15","Jurnalism radio","Asistent universitar V. Cernea","429/407/Bl. Central"),
    ("2025-10-03","18:30","20:00","Disciplina U","Dr., conf. univ. A. Colațchi","Blocul 2/ s. 102"),
    ("2025-10-03","20:15","21:45","Disciplina U","Dr., conf. univ. A. Colațchi","Blocul 2/ s. 102"),

    # 04.10.2025 (sâmbătă)
    ("2025-10-04","08:00","09:30","Disciplina U","Dr., conf. univ. A. Colațchi","Blocul 2/ s. 102"),
    ("2025-10-04","09:45","11:15","Disciplina U","Dr., conf. univ. A. Colațchi","Blocul 2/ s. 102"),
    ("2025-10-04","11:30","13:00","Știrea","Dr., conf. univ. M. Tacu","s. 432"),
    ("2025-10-04","13:15","14:45","Știrea","Dr., conf. univ. M. Tacu","s. 432"),
]

# ================== БАЗА ДАННЫХ ==================
SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,         -- YYYY-MM-DD
    time_start TEXT,            -- HH:MM
    time_end TEXT,              -- HH:MM
    title TEXT NOT NULL,
    teacher TEXT,
    room TEXT,
    group_code TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_date_group ON events(date, group_code);
"""

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        for stmt in SCHEMA.strip().split(";"):
            s = stmt.strip()
            if s:
                con.execute(s + ";")

def clear_group(group_code: str):
    with db() as con:
        con.execute("DELETE FROM events WHERE group_code=?", (group_code,))

def seed_schedule():
    clear_group(GROUP)
    with db() as con:
        con.executemany(
            "INSERT INTO events(date, time_start, time_end, title, teacher, room, group_code) "
            "VALUES(?,?,?,?,?,?,?)",
            [(d, t1, t2, title, teacher, room, GROUP) for (d, t1, t2, title, teacher, room) in SCHEDULE]
        )

# ================== УТИЛИТЫ/ФОРМАТ ==================
def now_local_date() -> date:
    return (datetime.utcnow() + timedelta(hours=TZ_OFFSET_HOURS)).date()

def week_bounds(any_day: date):
    start = any_day - timedelta(days=any_day.weekday())  # Monday
    end = start + timedelta(days=6)
    return start, end

def fetch_day(d: date):
    with db() as con:
        cur = con.execute(
            """SELECT * FROM events
               WHERE date=? AND group_code=?
               ORDER BY COALESCE(time_start,'99:99'), title""",
            (d.strftime("%Y-%m-%d"), GROUP),
        )
        return cur.fetchall()

def fetch_week(start: date, end: date):
    with db() as con:
        cur = con.execute(
            """SELECT * FROM events
               WHERE date BETWEEN ? AND ? AND group_code=?
               ORDER BY date, COALESCE(time_start,'99:99'), title""",
            (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), GROUP),
        )
        return cur.fetchall()

def fmt_pair(row: sqlite3.Row) -> str:
    t1 = row["time_start"] or ""
    t2 = row["time_end"] or ""
    time_part = f"{t1}-{t2}" if (t1 and t2) else (t1 or "—")
    title = row["title"] or ""
    teacher = row["teacher"] or ""
    room = row["room"] or ""
    line = f"• <b>{time_part}</b> · <i>{title}</i>"
    extras = []
    if teacher: extras.append(f"👩‍🏫 {teacher}")
    if room:    extras.append(f"🏫 <b>{room}</b>")
    if extras:
        line += "\n  " + " · ".join(extras)
    return line

def fmt_day(d: date, rows: list[sqlite3.Row]) -> str:
    head = f"📅 {d.strftime('%a, %d.%m.%Y')} — <b>{GROUP_LABEL}</b>"
    if not rows:
        return f"{head}\nЗанятий нет."
    return head + "\n" + "\n".join(fmt_pair(r) for r in rows)

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Сегодня"), KeyboardButton(text="🗂 Эта неделя")],
            [KeyboardButton(text="🗓 Выбрать день недели")],
        ],
        resize_keyboard=True,
    )

def days_keyboard(anchor: date):
    start, end = week_bounds(anchor)
    b = InlineKeyboardBuilder()

    # Без эмодзи в strftime (некоторым консолям не нравится)
    prev_txt = (start - timedelta(days=7)).strftime("%d.%m")
    next_txt = (start + timedelta(days=7)).strftime("%d.%m")
    mid_txt  = f"Неделя {start.strftime('%d.%m')}–{end.strftime('%d.%m')}"

    b.button(text=f"< {prev_txt}", callback_data=f"wk:{(start - timedelta(days=7)).isoformat()}")
    b.button(text=mid_txt,        callback_data="noop")
    b.button(text=f"{next_txt} >", callback_data=f"wk:{(start + timedelta(days=7)).isoformat()}")
    b.adjust(3)

    weekdays = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
    d = start
    for i in range(7):
        label = f"{weekdays[i]} {d.day:02d}"
        b.button(text=label, callback_data=f"d:{d.isoformat()}")
        d += timedelta(days=1)
    b.adjust(3,4)
    return b.as_markup()

async def safe_edit(message, *, text=None, reply_markup=None):
    try:
        if text is not None:
            await message.edit_text(text, reply_markup=reply_markup)
        else:
            await message.edit_reply_markup(reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            raise

# ================== БОТ ==================
router = Router()

@router.message(Command("start"))
async def cmd_start(m: Message):
    await m.answer(
        f"Привет! Показать расписание для <b>{GROUP_LABEL}</b>.\nВыбирай:",
        reply_markup=main_menu()
    )

@router.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer(
        "Команды:\n"
        "• 📅 Сегодня — расписание на сегодня\n"
        "• 🗂 Эта неделя — все дни недели\n"
        "• 🗓 Выбрать день недели — навигация кнопками\n"
        "• /reload — перезагрузить встроенное расписание в БД"
    )

@router.message(Command("reload"))
async def cmd_reload(m: Message):
    seed_schedule()
    await m.answer("🔄 Расписание перезалито в БД.")

@router.message(F.text == "📅 Сегодня")
async def today(m: Message):
    d = now_local_date()
    rows = fetch_day(d)
    await m.answer(fmt_day(d, rows), reply_markup=days_keyboard(d))

@router.message(F.text == "🗂 Эта неделя")
async def this_week(m: Message):
    start, end = week_bounds(now_local_date())
    rows = fetch_week(start, end)
    if not rows:
        return await m.answer("На эту неделю занятий нет.", reply_markup=days_keyboard(start))
    by = {}
    for r in rows:
        by.setdefault(r["date"], []).append(r)
    parts = []
    d = start
    while d <= end:
        parts.append(fmt_day(d, by.get(d.strftime("%Y-%m-%d"), [])))
        d += timedelta(days=1)
    await m.answer("\n\n".join(parts), reply_markup=days_keyboard(start))

@router.message(F.text == "🗓 Выбрать день недели")
async def pick_day(m: Message):
    await m.answer("Выбери день:", reply_markup=days_keyboard(now_local_date()))

@router.callback_query(F.data.startswith("wk:"))
async def change_week(c: CallbackQuery):
    anchor = date.fromisoformat(c.data.split(":")[1])
    await safe_edit(c.message, reply_markup=days_keyboard(anchor))
    await c.answer("Неделя обновлена")

@router.callback_query(F.data.startswith("d:"))
async def show_day(c: CallbackQuery):
    d = date.fromisoformat(c.data.split(":")[1])
    rows = fetch_day(d)
    await safe_edit(c.message, text=fmt_day(d, rows), reply_markup=days_keyboard(d))
    await c.answer()

async def main():
    init_db()
    seed_schedule()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
