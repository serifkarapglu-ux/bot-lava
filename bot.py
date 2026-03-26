import os
import sys
import logging
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    BotCommand, ChatMember,
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, Application,
)
from telegram.error import TelegramError

import db
import photo_utils

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bot-lava")

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    sys.exit("TELEGRAM_TOKEN ortam değişkeni eksik!")

ADMIN_ID = 6637073949

REQUIRED_CHANNELS = [
    {"username": "sadecebenchat",   "name": "Sadece Ben 💬",     "link": "https://t.me/sadecebenchat"},
    {"username": "dostlarhanesitr", "name": "Dostlar Hanesi 🏠", "link": "https://t.me/dostlarhanesitr"},
]

PRIVATE_GROUPS = [
    {"link": "https://t.me/+Un8PSU-WLthkZDY0", "name": "Özel Grup 1"},
    {"link": "https://t.me/+WpIO5smVM91mNTVk", "name": "Özel Grup 2"},
    {"link": "https://t.me/+lHyQOrt7aqc1NDA0", "name": "Özel Grup 3"},
]

CHANNEL_REWARD = 5
INVITE_REWARD = 10


# ─── Klavyeler ─────────────────────────────────────────────────────────────────

def main_menu_kb(user_id=None):
    rows = [
        [
            InlineKeyboardButton("💰 Bakiyem",          callback_data="bakiye"),
            InlineKeyboardButton("🛒 Mağaza",            callback_data="magaza"),
        ],
        [
            InlineKeyboardButton("📸 PP 4K",             callback_data="pp4k"),
            InlineKeyboardButton("🔄 Cinsiyet Değiştir", callback_data="cinsiyet"),
        ],
        [
            InlineKeyboardButton("🎁 Davet Et",          callback_data="davet"),
            InlineKeyboardButton("✅ Kanal/Grup Ödülü",  callback_data="odul"),
        ],
        [
            InlineKeyboardButton("📦 Siparişlerim",      callback_data="siparislerim"),
            InlineKeyboardButton("ℹ️ Yardım",            callback_data="yardim"),
        ],
    ]
    if user_id == ADMIN_ID:
        rows.append([InlineKeyboardButton("👑 Admin Paneli", callback_data="admin_panel")])
    return InlineKeyboardMarkup(rows)


def admin_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 Duyuru Gönder",    callback_data="admin_duyuru"),
            InlineKeyboardButton("📊 İstatistikler",    callback_data="admin_stats"),
        ],
        [
            InlineKeyboardButton("👥 Kullanıcı Sayısı", callback_data="admin_usercount"),
            InlineKeyboardButton("💰 Bakiye Ver",        callback_data="admin_bakiyever"),
        ],
        [
            InlineKeyboardButton("➕ Ürün Ekle",         callback_data="admin_urun_ekle"),
            InlineKeyboardButton("📋 Ürünleri Listele", callback_data="admin_urun_listele"),
        ],
        [
            InlineKeyboardButton("📣 Reklam Ekle",       callback_data="admin_reklam_ekle"),
            InlineKeyboardButton("📣 Reklam Gönder",     callback_data="admin_reklam_gonder"),
        ],
        [InlineKeyboardButton("🔙 Ana Menü", callback_data="ana_menu")],
    ])


# ─── Yardımcılar ───────────────────────────────────────────────────────────────

async def check_membership(bot, user_id: int) -> dict:
    results = {}
    for ch in REQUIRED_CHANNELS:
        try:
            m = await bot.get_chat_member(f"@{ch['username']}", user_id)
            results[ch["username"]] = m.status not in (ChatMember.BANNED, ChatMember.LEFT)
        except TelegramError:
            results[ch["username"]] = False
    return results


async def broadcast(bot, targets: list[int], text: str, parse_mode="Markdown"):
    sent = fail = 0
    for tid in targets:
        try:
            await bot.send_message(tid, text, parse_mode=parse_mode)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
    return sent, fail


# ─── Komutlar ──────────────────────────────────────────────────────────────────

async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = ctx.args
    invited_by = None

    if args and args[0].startswith("ref_"):
        try:
            invited_by = int(args[0][4:])
            if invited_by == user.id:
                invited_by = None
        except ValueError:
            pass

    is_new = db.register_user(user.id, user.username, user.first_name, invited_by)
    bal = db.get_balance(user.id)

    text = (
        f"🌋 *bot-lava'ya hoş geldin, {user.first_name}!*\n\n"
        f"💰 Bakiyen: *{bal} TL*\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 Arkadaşını davet et → +{INVITE_REWARD} TL\n"
        f"📺 Kanallara katıl     → +{CHANNEL_REWARD} TL\n"
        "📸 Fotoğraf 4K'ya çevir\n"
        "🔄 Cinsiyet değiştirici\n"
        "🛒 Ürün satın al\n"
        "📢 Duyuru & Reklam sistemi\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    if is_new and invited_by:
        text += f"\n\n✅ Davet linki ile geldin! Davet edene *+{INVITE_REWARD} TL* eklendi."

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_kb(user.id))


async def bakiye_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username, user.first_name)
    bal  = db.get_balance(user.id)
    inv  = db.get_invite_count(user.id)
    text = (
        f"💰 *Bakiye Bilgisi*\n\n"
        f"Mevcut Bakiye: *{bal} TL*\n"
        f"Davet Sayısı: *{inv} kişi*\n\n"
        f"Bakiye kazanma:\n"
        f"🎁 Davet → +{INVITE_REWARD} TL/kişi\n"
        f"📺 Kanal  → +{CHANNEL_REWARD} TL/kanal"
    )
    await update.message.reply_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎁 Davet Linkim",    callback_data="davet")],
            [InlineKeyboardButton("✅ Kanal Ödülü Al", callback_data="odul")],
        ])
    )


async def davet_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username, user.first_name)
    bot_username = (await ctx.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=ref_{user.id}"
    inv  = db.get_invite_count(user.id)
    await update.message.reply_text(
        f"🎁 *Davet Sistemi*\n\nDavet linkin:\n`{link}`\n\n"
        f"Bu linki paylaş, biri kaydolunca *+{INVITE_REWARD} TL* kazan!\n\n"
        f"Toplam davet: *{inv} kişi* → *{inv * INVITE_REWARD} TL*",
        parse_mode="Markdown"
    )


async def odul_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username, user.first_name)
    membership = await check_membership(ctx.bot, user.id)
    earned = 0
    report = "✅ *Kanal/Grup Üyelik Ödülleri*\n\n"
    for ch in REQUIRED_CHANNELS:
        uname = ch["username"]
        if membership.get(uname):
            given = db.give_channel_reward(user.id, uname, CHANNEL_REWARD)
            if given:
                report += f"✅ {ch['name']} → +{CHANNEL_REWARD} TL eklendi!\n"
                earned += CHANNEL_REWARD
            else:
                report += f"ℹ️ {ch['name']} → Ödül zaten alındı\n"
        else:
            report += f"❌ {ch['name']} → [Katıl]({ch['link']})\n"

    report += "\n📌 Özel gruplara da katıl:\n"
    for g in PRIVATE_GROUPS:
        report += f"• [{g['name']}]({g['link']})\n"

    if earned > 0:
        report += f"\n🎉 Bu işlemde *+{earned} TL* kazandın!"

    await update.message.reply_text(report, parse_mode="Markdown", disable_web_page_preview=True)


async def magaza_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username, user.first_name)
    products = db.get_products()
    if not products:
        await update.message.reply_text("🛒 Şu an ürün bulunmuyor.")
        return
    buttons = [
        [InlineKeyboardButton(f"{p['name']} — {p['price']} TL", callback_data=f"urun_{p['id']}")]
        for p in products
    ]
    await update.message.reply_text("🛒 *Mağaza* — Bir ürün seç:", parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup(buttons))


async def siparislerim_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username, user.first_name)
    orders = db.get_orders(user.id)
    if not orders:
        await update.message.reply_text("📦 Henüz siparişin yok.")
        return
    text = "📦 *Siparişlerin:*\n\n"
    for o in orders[:10]:
        emoji = {"beklemede": "⏳", "tamamlandi": "✅", "iptal": "❌"}.get(o["status"], "❓")
        text += f"{emoji} {o['name']} — {o['total_price']} TL ({o['created_at'][:10]})\n"
    await update.message.reply_text(text, parse_mode="Markdown")


async def pp4k_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username, user.first_name)
    db.set_photo_wait(user.id, "pp4k")
    await update.message.reply_text("📸 *PP 4K Yapıcı*\n\nFotoğrafını gönder!", parse_mode="Markdown")


async def cinsiyet_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username, user.first_name)
    await update.message.reply_text(
        "🔄 *Cinsiyet Değiştirici*\n\nYönü seç:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👩 Erkek → Kız",   callback_data="cinsiyet_kiz"),
                InlineKeyboardButton("👨 Kız → Erkek",   callback_data="cinsiyet_erkek"),
            ]
        ])
    )


async def duyuru_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bu komut sadece admin içindir!")
        return
    if not ctx.args:
        await update.message.reply_text("Kullanım: /duyuru <mesaj metni>")
        return

    text = "📢 *DUYURU*\n\n" + " ".join(ctx.args)
    users  = db.get_all_users()
    groups = db.get_all_groups()
    targets = list(set(users + groups))

    msg = await update.message.reply_text(f"📢 {len(targets)} hedefe gönderiliyor...")
    sent, fail = await broadcast(ctx.bot, targets, text)
    await msg.edit_text(f"✅ Duyuru tamamlandı!\n✅ Başarılı: {sent}\n❌ Başarısız: {fail}")


async def iptal_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.set_photo_wait(user.id, None)
    ctx.user_data.clear()
    await update.message.reply_text("✅ İşlem iptal edildi.", reply_markup=main_menu_kb(user.id))


# ─── Callback Handler ──────────────────────────────────────────────────────────

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user  = query.from_user
    data  = query.data
    await query.answer()

    # ── Ana Menü ──
    if data == "ana_menu":
        bal = db.get_balance(user.id)
        await query.edit_message_text(
            f"🌋 *Ana Menü* — Bakiye: *{bal} TL*",
            parse_mode="Markdown",
            reply_markup=main_menu_kb(user.id)
        )

    # ── Bakiye ──
    elif data == "bakiye":
        bal = db.get_balance(user.id)
        inv = db.get_invite_count(user.id)
        await query.edit_message_text(
            f"💰 *Bakiye Bilgisi*\n\n"
            f"Mevcut Bakiye: *{bal} TL*\n"
            f"Davet Sayısı: *{inv} kişi*\n\n"
            f"🎁 Davet → +{INVITE_REWARD} TL/kişi\n"
            f"📺 Kanal  → +{CHANNEL_REWARD} TL/kanal",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎁 Davet Linkim",    callback_data="davet")],
                [InlineKeyboardButton("✅ Kanal Ödülü Al", callback_data="odul")],
                [InlineKeyboardButton("🔙 Geri",            callback_data="ana_menu")],
            ])
        )

    # ── Davet ──
    elif data == "davet":
        bot_me = await ctx.bot.get_me()
        link = f"https://t.me/{bot_me.username}?start=ref_{user.id}"
        inv  = db.get_invite_count(user.id)
        await query.edit_message_text(
            f"🎁 *Davet Sistemi*\n\nDavet linkin:\n`{link}`\n\n"
            f"Biri bu linkle kaydolunca *+{INVITE_REWARD} TL* kazan!\n\n"
            f"Toplam: *{inv} kişi* — *{inv * INVITE_REWARD} TL* kazanıldı",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Geri", callback_data="ana_menu")]])
        )

    # ── Ödül ──
    elif data == "odul":
        membership = await check_membership(ctx.bot, user.id)
        earned = 0
        report = "✅ *Kanal/Grup Üyelik Ödülleri*\n\n"
        for ch in REQUIRED_CHANNELS:
            uname = ch["username"]
            if membership.get(uname):
                given = db.give_channel_reward(user.id, uname, CHANNEL_REWARD)
                if given:
                    report += f"✅ {ch['name']} → +{CHANNEL_REWARD} TL eklendi!\n"
                    earned += CHANNEL_REWARD
                else:
                    report += f"ℹ️ {ch['name']} → Zaten alındı\n"
            else:
                report += f"❌ {ch['name']} → [Katıl]({ch['link']})\n"
        report += "\n📌 Özel gruplara katıl:\n"
        for g in PRIVATE_GROUPS:
            report += f"• [{g['name']}]({g['link']})\n"
        if earned > 0:
            report += f"\n🎉 *+{earned} TL* kazandın!"
        await query.edit_message_text(
            report, parse_mode="Markdown", disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Geri", callback_data="ana_menu")]])
        )

    # ── Mağaza ──
    elif data == "magaza":
        products = db.get_products()
        if not products:
            await query.edit_message_text("🛒 Şu an ürün bulunmuyor.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Geri", callback_data="ana_menu")]]))
            return
        buttons = [
            [InlineKeyboardButton(f"{p['name']} — {p['price']} TL", callback_data=f"urun_{p['id']}")]
            for p in products
        ]
        buttons.append([InlineKeyboardButton("🔙 Geri", callback_data="ana_menu")])
        await query.edit_message_text("🛒 *Mağaza* — Bir ürün seç:", parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup(buttons))

    # ── Ürün Detay ──
    elif data.startswith("urun_"):
        pid = int(data.split("_")[1])
        p   = db.get_product(pid)
        if not p:
            await query.answer("Ürün bulunamadı!", show_alert=True)
            return
        bal = db.get_balance(user.id)
        await query.edit_message_text(
            f"🏷️ *{p['name']}*\n\n"
            f"📝 {p['description']}\n"
            f"💰 Fiyat: *{p['price']} TL*\n"
            f"📦 Stok: {'Sınırsız' if p['stock'] < 0 else p['stock']}\n"
            f"🗂️ Kategori: {p['category']}\n\n"
            f"Senin bakiyen: *{bal} TL*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✅ Satın Al — {p['price']} TL", callback_data=f"satin_{pid}")],
                [InlineKeyboardButton("🔙 Mağazaya Dön", callback_data="magaza")],
            ])
        )

    # ── Satın Al ──
    elif data.startswith("satin_"):
        pid = int(data.split("_")[1])
        p   = db.get_product(pid)
        if not p:
            await query.answer("Ürün bulunamadı!", show_alert=True)
            return
        if p["stock"] == 0:
            await query.answer("Stok tükendi!", show_alert=True)
            return
        ok = db.deduct_balance(user.id, p["price"])
        if not ok:
            await query.answer("Yetersiz bakiye! Davet et veya kanallara katıl.", show_alert=True)
            return
        db.create_order(user.id, pid, 1, p["price"])
        await query.edit_message_text(
            f"✅ *Satın alma başarılı!*\n\nÜrün: *{p['name']}*\nTutar: *{p['price']} TL*\n\n"
            "Siparişin alındı. Admin yakında seninle iletişime geçecek. 🙏",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ana Menü", callback_data="ana_menu")]])
        )
        try:
            await ctx.bot.send_message(
                ADMIN_ID,
                f"🛒 *Yeni Sipariş!*\n"
                f"👤 [{user.first_name}](tg://user?id={user.id}) (ID: `{user.id}`)\n"
                f"📦 {p['name']}\n💰 {p['price']} TL",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    # ── Siparişlerim ──
    elif data == "siparislerim":
        orders = db.get_orders(user.id)
        if not orders:
            txt = "📦 Henüz siparişin yok."
        else:
            txt = "📦 *Siparişlerin:*\n\n"
            for o in orders[:10]:
                e = {"beklemede": "⏳", "tamamlandi": "✅", "iptal": "❌"}.get(o["status"], "❓")
                txt += f"{e} {o['name']} — {o['total_price']} TL ({o['created_at'][:10]})\n"
        await query.edit_message_text(txt, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Geri", callback_data="ana_menu")]]))

    # ── PP 4K ──
    elif data == "pp4k":
        db.set_photo_wait(user.id, "pp4k")
        await query.edit_message_text(
            "📸 *PP 4K Yapıcı*\n\nFotoğrafını gönder, 4K'ya çevireyim!\n_/iptal ile çıkabilirsin_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 İptal", callback_data="ana_menu")]])
        )

    # ── Cinsiyet ──
    elif data == "cinsiyet":
        await query.edit_message_text(
            "🔄 *Cinsiyet Değiştirici*\n\nHangi yönde dönüştürmek istiyorsun?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("👩 Erkek → Kız",  callback_data="cinsiyet_kiz"),
                    InlineKeyboardButton("👨 Kız → Erkek",  callback_data="cinsiyet_erkek"),
                ],
                [InlineKeyboardButton("🔙 Geri", callback_data="ana_menu")],
            ])
        )

    elif data in ("cinsiyet_kiz", "cinsiyet_erkek"):
        to_female = (data == "cinsiyet_kiz")
        db.set_photo_wait(user.id, "kiz" if to_female else "erkek")
        yön = "Erkek → Kız" if to_female else "Kız → Erkek"
        await query.edit_message_text(
            f"🔄 *{yön}*\n\nFotoğrafını gönder!\n_(İşlem 1-2 dakika sürebilir)_\n_/iptal ile çıkabilirsin_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 İptal", callback_data="ana_menu")]])
        )

    # ── Yardım ──
    elif data == "yardim":
        await query.edit_message_text(
            "ℹ️ *Yardım Menüsü*\n\n"
            "🌋 *bot-lava* — Çok Fonksiyonlu Bot\n\n"
            "*Komutlar:*\n"
            "/start — Ana menü\n"
            "/bakiye — Bakiye sorgula\n"
            "/davet — Davet linki al\n"
            "/odul — Kanal ödülü al\n"
            "/magaza — Ürünlere bak\n"
            "/siparislerim — Siparişlerin\n"
            "/pp4k — Fotoğraf 4K yap\n"
            "/cinsiyet — Cinsiyet değiştir\n"
            "/iptal — İşlemi iptal et\n\n"
            "*Bakiye Kazanma:*\n"
            f"• Kanal üyeliği → +{CHANNEL_REWARD} TL\n"
            f"• Arkadaş daveti → +{INVITE_REWARD} TL\n\n"
            "📞 Destek: @sadecebenchat",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Geri", callback_data="ana_menu")]])
        )

    # ── Admin Paneli ──
    elif data == "admin_panel":
        if user.id != ADMIN_ID:
            await query.answer("⛔ Yetkisiz erişim!", show_alert=True)
            return
        await query.edit_message_text("👑 *Admin Paneli*\n\nBir işlem seç:", parse_mode="Markdown",
                                      reply_markup=admin_kb())

    elif data == "admin_stats":
        if user.id != ADMIN_ID:
            await query.answer("⛔ Yetkisiz!", show_alert=True)
            return
        s = db.get_stats()
        await query.edit_message_text(
            f"📊 *İstatistikler*\n\n"
            f"👥 Toplam Kullanıcı: *{s['users']}*\n"
            f"🏘️ Toplam Grup: *{s['groups']}*\n"
            f"📦 Toplam Sipariş: *{s['orders']}*\n"
            f"💰 Toplam Gelir: *{s['revenue']} TL*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Geri", callback_data="admin_panel")]])
        )

    elif data == "admin_usercount":
        if user.id != ADMIN_ID:
            await query.answer("⛔ Yetkisiz!", show_alert=True)
            return
        count = len(db.get_all_users())
        await query.answer(f"Toplam {count} kullanıcı kayıtlı!", show_alert=True)

    elif data == "admin_bakiyever":
        if user.id != ADMIN_ID:
            await query.answer("⛔ Yetkisiz!", show_alert=True)
            return
        ctx.user_data["admin_state"] = "bakiye_ver_id"
        await query.edit_message_text(
            "💰 Kullanıcı ID'sini gir:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 İptal", callback_data="admin_panel")]])
        )

    elif data == "admin_urun_ekle":
        if user.id != ADMIN_ID:
            await query.answer("⛔ Yetkisiz!", show_alert=True)
            return
        ctx.user_data["admin_state"] = "urun_ekle_name"
        await query.edit_message_text(
            "➕ *Ürün Ekle*\n\nÜrün adını gir:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 İptal", callback_data="admin_panel")]])
        )

    elif data == "admin_urun_listele":
        if user.id != ADMIN_ID:
            await query.answer("⛔ Yetkisiz!", show_alert=True)
            return
        products = db.get_products(active_only=False)
        txt = "📋 *Ürün Listesi:*\n\n"
        for p in products:
            durum = "✅" if p["active"] else "❌"
            txt += f"{durum} [{p['id']}] {p['name']} — {p['price']} TL\n"
        await query.edit_message_text(txt, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Geri", callback_data="admin_panel")]]))

    elif data == "admin_duyuru":
        if user.id != ADMIN_ID:
            await query.answer("⛔ Yetkisiz!", show_alert=True)
            return
        ctx.user_data["admin_state"] = "duyuru_yaz"
        await query.edit_message_text(
            "📢 *Duyuru Sistemi*\n\nDuyuru metnini gir:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 İptal", callback_data="admin_panel")]])
        )

    elif data == "admin_reklam_ekle":
        if user.id != ADMIN_ID:
            await query.answer("⛔ Yetkisiz!", show_alert=True)
            return
        ctx.user_data["admin_state"] = "reklam_ekle"
        await query.edit_message_text(
            "📣 *Reklam Ekle*\n\nReklam metnini gir:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 İptal", callback_data="admin_panel")]])
        )

    elif data == "admin_reklam_gonder":
        if user.id != ADMIN_ID:
            await query.answer("⛔ Yetkisiz!", show_alert=True)
            return
        ads = db.get_active_ads()
        if not ads:
            await query.answer("Aktif reklam yok!", show_alert=True)
            return
        await query.answer("Reklam gönderimi başlatıldı!", show_alert=True)
        users = db.get_all_users()
        for ad in ads:
            asyncio.create_task(broadcast(ctx.bot, users, f"📣 *Reklam*\n\n{ad['content']}"))


# ─── Fotoğraf Handler ──────────────────────────────────────────────────────────

async def photo_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    state = db.get_photo_wait(user.id)

    if not state:
        return

    photo = update.message.photo
    if not photo:
        await update.message.reply_text("❌ Lütfen bir fotoğraf gönder.")
        return

    msg  = await update.message.reply_text("⏳ Fotoğraf işleniyor...")
    file = await ctx.bot.get_file(photo[-1].file_id)
    raw  = bytes(await file.download_as_bytearray())

    db.set_photo_wait(user.id, None)

    if state == "pp4k":
        await msg.edit_text("📸 4K'ya dönüştürülüyor...")
        try:
            result = photo_utils.upscale_4k(raw)
            await update.message.reply_photo(
                result,
                caption="✅ *4K fotoğrafın hazır!* 🌋",
                parse_mode="Markdown"
            )
            await msg.delete()
        except Exception as e:
            logger.error(f"4K hatası: {e}")
            await msg.edit_text("❌ 4K dönüşümde hata oluştu.")

    elif state in ("kiz", "erkek"):
        to_female = (state == "kiz")
        yön = "Erkek → Kız" if to_female else "Kız → Erkek"
        await msg.edit_text(f"🔄 {yön} dönüşümü yapılıyor... _(1-2 dk)_", parse_mode="Markdown")
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, photo_utils.gender_swap, raw, to_female
            )
            if result:
                await update.message.reply_photo(
                    result,
                    caption=f"✅ *{yön} dönüşümü tamamlandı!* 🌋",
                    parse_mode="Markdown"
                )
                await msg.delete()
            else:
                await msg.edit_text("⚠️ AI servisi meşgul, birkaç dakika sonra tekrar dene.")
        except Exception as e:
            logger.error(f"Cinsiyet hatası: {e}")
            await msg.edit_text("❌ İşlem sırasında hata oluştu.")


# ─── Metin Handler (Admin akışı) ───────────────────────────────────────────────

async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    state = ctx.user_data.get("admin_state")
    if not state:
        return

    text = update.message.text or ""

    if state == "duyuru_yaz":
        ctx.user_data.pop("admin_state")
        targets = list(set(db.get_all_users() + db.get_all_groups()))
        msg = await update.message.reply_text(f"📢 {len(targets)} hedefe gönderiliyor...")
        sent, fail = await broadcast(ctx.bot, targets, f"📢 *DUYURU*\n\n{text}")
        await msg.edit_text(
            f"✅ Duyuru tamamlandı!\n✅ Başarılı: {sent}\n❌ Başarısız: {fail}",
            reply_markup=admin_kb()
        )

    elif state == "reklam_ekle":
        ctx.user_data.pop("admin_state")
        db.add_ad(text)
        await update.message.reply_text("✅ Reklam eklendi!", reply_markup=admin_kb())

    elif state == "bakiye_ver_id":
        try:
            tid = int(text.strip())
            ctx.user_data["admin_state"]    = "bakiye_ver_miktar"
            ctx.user_data["admin_target_id"] = tid
            await update.message.reply_text(f"💰 {tid} için miktar gir (TL):")
        except ValueError:
            ctx.user_data.pop("admin_state", None)
            await update.message.reply_text("❌ Geçersiz ID!", reply_markup=admin_kb())

    elif state == "bakiye_ver_miktar":
        try:
            amount = float(text.strip())
            tid = ctx.user_data.pop("admin_target_id", None)
            ctx.user_data.pop("admin_state")
            db.add_balance(tid, amount)
            await update.message.reply_text(
                f"✅ {tid} kullanıcısına *{amount} TL* eklendi!",
                parse_mode="Markdown", reply_markup=admin_kb()
            )
            try:
                await ctx.bot.send_message(
                    tid,
                    f"🎉 Hesabına *{amount} TL* eklendi!\n💰 Yeni bakiyen: *{db.get_balance(tid)} TL*",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        except ValueError:
            ctx.user_data.pop("admin_state", None)
            await update.message.reply_text("❌ Geçersiz miktar!", reply_markup=admin_kb())

    elif state == "urun_ekle_name":
        ctx.user_data["new_product"]  = {"name": text}
        ctx.user_data["admin_state"]  = "urun_ekle_desc"
        await update.message.reply_text("📝 Açıklama gir:")

    elif state == "urun_ekle_desc":
        ctx.user_data["new_product"]["description"] = text
        ctx.user_data["admin_state"] = "urun_ekle_price"
        await update.message.reply_text("💰 Fiyat gir (TL):")

    elif state == "urun_ekle_price":
        try:
            ctx.user_data["new_product"]["price"] = float(text.strip())
            ctx.user_data["admin_state"] = "urun_ekle_stock"
            await update.message.reply_text("📦 Stok gir (-1 = sınırsız):")
        except ValueError:
            ctx.user_data.pop("admin_state", None)
            await update.message.reply_text("❌ Geçersiz fiyat!", reply_markup=admin_kb())

    elif state == "urun_ekle_stock":
        try:
            ctx.user_data["new_product"]["stock"] = int(text.strip())
            ctx.user_data["admin_state"] = "urun_ekle_cat"
            await update.message.reply_text("🗂️ Kategori gir (örn: Üyelik, Paket, Reklam):")
        except ValueError:
            ctx.user_data.pop("admin_state", None)
            await update.message.reply_text("❌ Geçersiz stok!", reply_markup=admin_kb())

    elif state == "urun_ekle_cat":
        p = ctx.user_data.pop("new_product", {})
        ctx.user_data.pop("admin_state")
        p["category"] = text
        db.add_product(p["name"], p["description"], p["price"], p["stock"], p["category"])
        await update.message.reply_text(
            f"✅ *{p['name']}* ürünü eklendi!",
            parse_mode="Markdown", reply_markup=admin_kb()
        )


# ─── Gruba Eklenme ─────────────────────────────────────────────────────────────

async def new_member_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    for member in update.message.new_chat_members:
        if member.id == ctx.bot.id:
            added_by = update.message.from_user
            db.add_group(chat.id, chat.title or "", added_by.id if added_by else 0)
            try:
                await ctx.bot.send_message(
                    chat.id,
                    "🌋 *bot-lava aktif!*\n\nMerhaba! Kullanıcılarınıza hizmet etmeye hazırım.\n"
                    "Komutlar için /start yazabilirsiniz.",
                    parse_mode="Markdown"
                )
            except Exception:
                pass


# ─── Başlangıç ─────────────────────────────────────────────────────────────────

async def post_init(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start",        "Ana menüyü aç"),
        BotCommand("bakiye",       "Bakiyeni gör"),
        BotCommand("davet",        "Davet linki al"),
        BotCommand("odul",         "Kanal ödüllerini al"),
        BotCommand("magaza",       "Ürünlere bak"),
        BotCommand("siparislerim", "Siparişlerin"),
        BotCommand("pp4k",         "Fotoğraf 4K yap"),
        BotCommand("cinsiyet",     "Cinsiyet değiştir"),
        BotCommand("iptal",        "İşlemi iptal et"),
        BotCommand("duyuru",       "Duyuru gönder (Admin)"),
    ])
    logger.info("Bot komutları ayarlandı.")


def start_keepalive_server():
    port = int(os.environ.get("PORT", 8000))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"bot-lava calisiyor!")

        def log_message(self, *args):
            pass

    server = HTTPServer(("0.0.0.0", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Keep-alive sunucusu port {port} üzerinde başlatıldı.")


def main():
    db.init_db()
    logger.info("Veritabanı hazır.")
    start_keepalive_server()

    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start",        start_cmd))
    app.add_handler(CommandHandler("bakiye",       bakiye_cmd))
    app.add_handler(CommandHandler("davet",        davet_cmd))
    app.add_handler(CommandHandler("odul",         odul_cmd))
    app.add_handler(CommandHandler("magaza",       magaza_cmd))
    app.add_handler(CommandHandler("siparislerim", siparislerim_cmd))
    app.add_handler(CommandHandler("pp4k",         pp4k_cmd))
    app.add_handler(CommandHandler("cinsiyet",     cinsiyet_cmd))
    app.add_handler(CommandHandler("duyuru",       duyuru_cmd))
    app.add_handler(CommandHandler("iptal",        iptal_cmd))

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, photo_handler))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        text_handler
    ))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member_handler))

    logger.info("Polling modu başlatılıyor...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
        poll_interval=1.0,
        timeout=30,
    )


if __name__ == "__main__":
    main()
