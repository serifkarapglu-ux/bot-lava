import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "bot_data.db")

def get_conn():
    conn = sqlite3.connect("yeni.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        balance REAL DEFAULT 0,
        joined_at TEXT DEFAULT (datetime('now')),
        invited_by INTEGER,
        photo_wait TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS channel_rewards (
        user_id INTEGER,
        channel_id TEXT,
        PRIMARY KEY (user_id, channel_id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        stock INTEGER DEFAULT -1,
        category TEXT DEFAULT 'Genel',
        active INTEGER DEFAULT 1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        quantity INTEGER DEFAULT 1,
        total_price REAL,
        status TEXT DEFAULT 'beklemede',
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS invites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inviter_id INTEGER,
        invitee_id INTEGER,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        media_file_id TEXT,
        media_type TEXT,
        active INTEGER DEFAULT 1,
        views INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS groups_added (
        chat_id INTEGER PRIMARY KEY,
        chat_title TEXT,
        added_by INTEGER,
        added_at TEXT DEFAULT (datetime('now'))
    )""")

    if c.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO products (name, description, price, stock, category) VALUES (?,?,?,?,?)",
            [
                ("Premium Üyelik", "30 günlük premium üyelik paketi ✨", 50.0, 100, "Üyelik"),
                ("VIP Paket", "Özel VIP içerik ve ayrıcalıklar 👑", 100.0, 50, "Paket"),
                ("Reklam Paketi", "500 kullanıcıya reklam gönderimi 📢", 200.0, 999, "Reklam"),
                ("Destek Paketi", "7/24 öncelikli destek hizmeti 🛡️", 75.0, 999, "Destek"),
            ]
        )

    conn.commit()
    conn.close()

def register_user(user_id, username, first_name, invited_by=None):
    conn = get_conn()
    c = conn.cursor()
    existing = c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)).fetchone()
    if not existing:
        c.execute(
            "INSERT INTO users (user_id, username, first_name, invited_by) VALUES (?,?,?,?)",
            (user_id, username, first_name, invited_by)
        )
        if invited_by:
            c.execute("UPDATE users SET balance = balance + 10 WHERE user_id=?", (invited_by,))
            c.execute("INSERT INTO invites (inviter_id, invitee_id) VALUES (?,?)", (invited_by, user_id))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def get_user(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_balance(user_id):
    conn = get_conn()
    row = conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return round(row["balance"], 2) if row else 0.0

def add_balance(user_id, amount):
    conn = get_conn()
    conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def deduct_balance(user_id, amount):
    conn = get_conn()
    bal = conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
    if not bal or bal["balance"] < amount:
        conn.close()
        return False
    conn.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()
    return True

def set_balance(user_id, amount):
    conn = get_conn()
    conn.execute("UPDATE users SET balance = ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def check_channel_reward(user_id, channel_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM channel_rewards WHERE user_id=? AND channel_id=?",
        (user_id, str(channel_id))
    ).fetchone()
    conn.close()
    return row is not None

def give_channel_reward(user_id, channel_id, amount=5):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO channel_rewards (user_id, channel_id) VALUES (?,?)",
            (user_id, str(channel_id))
        )
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def get_all_users():
    conn = get_conn()
    rows = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    return [r["user_id"] for r in rows]

def get_all_groups():
    conn = get_conn()
    rows = conn.execute("SELECT chat_id FROM groups_added").fetchall()
    conn.close()
    return [r["chat_id"] for r in rows]

def add_group(chat_id, chat_title, added_by):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO groups_added (chat_id, chat_title, added_by) VALUES (?,?,?)",
        (chat_id, chat_title, added_by)
    )
    conn.commit()
    conn.close()

def get_products(active_only=True):
    conn = get_conn()
    q = "SELECT * FROM products WHERE active=1" if active_only else "SELECT * FROM products"
    rows = conn.execute(q).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_product(product_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_order(user_id, product_id, quantity, total_price):
    conn = get_conn()
    conn.execute(
        "INSERT INTO orders (user_id, product_id, quantity, total_price) VALUES (?,?,?,?)",
        (user_id, product_id, quantity, total_price)
    )
    conn.commit()
    conn.close()

def get_orders(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT o.*, p.name FROM orders o JOIN products p ON o.product_id=p.id WHERE o.user_id=? ORDER BY o.created_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats():
    conn = get_conn()
    users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    orders = conn.execute("SELECT COUNT(*) as c FROM orders").fetchone()["c"]
    revenue = conn.execute("SELECT COALESCE(SUM(total_price),0) as s FROM orders WHERE status='tamamlandi'").fetchone()["s"]
    groups = conn.execute("SELECT COUNT(*) as c FROM groups_added").fetchone()["c"]
    conn.close()
    return {"users": users, "orders": orders, "revenue": revenue, "groups": groups}

def add_ad(content, file_id=None, media_type=None):
    conn = get_conn()
    conn.execute("INSERT INTO ads (content, media_file_id, media_type) VALUES (?,?,?)", (content, file_id, media_type))
    conn.commit()
    conn.close()

def get_active_ads():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM ads WHERE active=1").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_product(name, description, price, stock, category):
    conn = get_conn()
    conn.execute(
        "INSERT INTO products (name, description, price, stock, category) VALUES (?,?,?,?,?)",
        (name, description, price, stock, category)
    )
    conn.commit()
    conn.close()

def toggle_product(product_id):
    conn = get_conn()
    conn.execute("UPDATE products SET active = 1-active WHERE id=?", (product_id,))
    conn.commit()
    conn.close()

def get_invite_count(user_id):
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) as c FROM invites WHERE inviter_id=?", (user_id,)).fetchone()
    conn.close()
    return row["c"] if row else 0

def set_photo_wait(user_id, state):
    conn = get_conn()
    conn.execute("UPDATE users SET photo_wait=? WHERE user_id=?", (state, user_id))
    conn.commit()
    conn.close()

def get_photo_wait(user_id):
    conn = get_conn()
    row = conn.execute("SELECT photo_wait FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row["photo_wait"] if row else None
