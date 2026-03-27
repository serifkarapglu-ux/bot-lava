import logging
import sqlite3
import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from datetime import datetime

# Logging aktif
logging.basicConfig(level=logging.INFO)

# Bot token - Environment Variable üzerinden alıyoruz (güvenli)
API_TOKEN = os.getenv("TOKEN")
if not API_TOKEN:
    raise Exception("⚠️ TOKEN environment variable bulunamadı!")

# Bot ve Dispatcher oluştur
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# SQLite bağlantısı
conn = sqlite3.connect("bot.db")
cursor = conn.cursor()

# Kullanıcı tablosu
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    referrer INTEGER,
    last_daily TEXT
)
""")

# Görev tablosu
cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    link TEXT,
    reward INTEGER
)
""")

# Çekim tablosu
cursor.execute("""
CREATE TABLE IF NOT EXISTS withdrawals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    status TEXT
)
""")

conn.commit()

# KULLANICI EKLE
def add_user(user_id, ref=None):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO users (user_id, referrer) VALUES (?, ?)", (user_id, ref))
        conn.commit()

# BAKİYE AL
def get_balance(user_id):
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone()[0]

# BAKİYE EKLE
def add_balance(user_id, amount):
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.commit()

# /start
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    ref = message.get_args()
    add_user(message.from_user.id, ref)
    await message.answer("👋 Hoş geldin!\n\n💰 Para kazanmak için görev yap!")

# BAKİYE
@dp.message_handler(commands=['bakiye'])
async def balance(message: types.Message):
    bal = get_balance(message.from_user.id)
    await message.answer(f"💰 Bakiyen: {bal}₺")

# GÜNLÜK ÖDÜL
@dp.message_handler(commands=['gunluk'])
async def daily(message: types.Message):
    user_id = message.from_user.id
    today = datetime.now().date()

    cursor.execute("SELECT last_daily FROM users WHERE user_id=?", (user_id,))
    last = cursor.fetchone()[0]

    if last == str(today):
        await message.answer("❌ Bugün zaten aldın")
        return

    add_balance(user_id, 5)
    cursor.execute("UPDATE users SET last_daily=? WHERE user_id=?", (str(today), user_id))
    conn.commit()

    await message.answer("🎁 Günlük 5₺ kazandın!")

# GÖREVLER
@dp.message_handler(commands=['gorevler'])
async def tasks(message: types.Message):
    cursor.execute("SELECT * FROM tasks")
    tasks = cursor.fetchall()

    text = "🎯 Görevler:\n\n"
    for t in tasks:
        text += f"{t[0]}. {t[1]} → {t[2]}₺\n"

    await message.answer(text)

# GÖREV EKLE (ADMIN)
ADMIN_ID = 123456789

@dp.message_handler(commands=['addtask'])
async def add_task(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    args = message.get_args().split()
    link = args[0]
    reward = int(args[1])

    cursor.execute("INSERT INTO tasks (link, reward) VALUES (?, ?)", (link, reward))
    conn.commit()

    await message.answer("✅ Görev eklendi")

# ÇEKİM
@dp.message_handler(commands=['cekim'])
async def withdraw(message: types.Message):
    user_id = message.from_user.id
    try:
        amount = int(message.get_args())
    except:
        await message.answer("❌ Doğru kullanım: /cekim 50")
        return

    if get_balance(user_id) < amount:
        await message.answer("❌ Yetersiz bakiye")
        return

    cursor.execute("INSERT INTO withdrawals (user_id, amount, status) VALUES (?, ?, ?)", (user_id, amount, "pending"))
    conn.commit()

    await message.answer("💸 Çekim talebi alındı")

# BOT BAŞLAT
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
