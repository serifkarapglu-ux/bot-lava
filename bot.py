import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# LOG
logging.basicConfig(level=logging.INFO)

TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Basit hafıza (db yerine)
users = {}

REQUIRED_CHANNELS = ["sadecebenchat", "dostlarhanesitr"]

# ─── Yardımcılar ───

def get_user(user_id):
    if user_id not in users:
        users[user_id] = {
            "balance": 0,
            "invites": 0,
            "rewarded": []
        }
    return users[user_id]

async def check_channels(bot, user_id):
    results = {}
    for ch in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(f"@{ch}", user_id)
            results[ch] = member.status not in ("left", "kicked")
        except:
            results[ch] = False
    return results

# ─── Menü ───

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Bakiye", callback_data="bakiye")],
        [InlineKeyboardButton("🎁 Davet", callback_data="davet")],
        [InlineKeyboardButton("✅ Ödül Al", callback_data="odul")]
    ])

# ─── Komutlar ───

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = get_user(user.id)

    # davet sistemi
    if ctx.args:
        if ctx.args[0].startswith("ref_"):
            ref_id = int(ctx.args[0].split("_")[1])
            if ref_id != user.id:
                get_user(ref_id)["balance"] += 10

    await update.message.reply_text(
        f"Hoşgeldin {user.first_name}!\nBakiyen: {u['balance']} TL",
        reply_markup=menu()
    )

async def bakiye(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = get_user(user.id)

    await update.message.reply_text(
        f"💰 Bakiyen: {u['balance']} TL\n🎁 Davet: {u['invites']}",
        reply_markup=menu()
    )

async def davet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_username = (await ctx.bot.get_me()).username

    link = f"https://t.me/{bot_username}?start=ref_{user.id}"

    await update.message.reply_text(
        f"Davet linkin:\n{link}\n\nHer davet +10 TL"
    )

async def odul(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = get_user(user.id)

    results = await check_channels(ctx.bot, user.id)

    text = ""
    earned = 0

    for ch, ok in results.items():
        if ok:
            if ch not in u["rewarded"]:
                u["balance"] += 5
                u["rewarded"].append(ch)
                earned += 5
                text += f"✅ {ch} +5 TL\n"
            else:
                text += f"ℹ️ {ch} zaten alındı\n"
        else:
            text += f"❌ @{ch} katıl\n"

    if earned > 0:
        text += f"\nToplam +{earned} TL kazandın"

    await update.message.reply_text(text, reply_markup=menu())

# ─── Butonlar ───

async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "bakiye":
        await bakiye(update, ctx)

    elif query.data == "davet":
        await davet(update, ctx)

    elif query.data == "odul":
        await odul(update, ctx)

# ─── MAIN ───

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))

print("Bot çalışıyor...")

app.run_polling()
