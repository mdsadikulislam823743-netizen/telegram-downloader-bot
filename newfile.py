# ================= INSTALL =================
# pip install python-telegram-bot yt-dlp

import os
import time
from urllib.parse import urlparse

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

import yt_dlp

# ================= CONFIG =================
BOT_TOKEN = "BOT_TOKEN"

MAX_DOWNLOADS_PER_USER = 2
COOLDOWN = 10  # seconds
DOWNLOAD_PATH = "downloads"

# ================= MEMORY =================
user_limits = {}
user_last_used = {}

# ================= HELPERS =================
def is_valid_url(text):
    parsed = urlparse(text)
    return parsed.scheme in ("http", "https") and parsed.netloc

def check_limit(uid):
    return user_limits.get(uid, 0) < MAX_DOWNLOADS_PER_USER

def increase_limit(uid):
    user_limits[uid] = user_limits.get(uid, 0) + 1

def check_cooldown(uid):
    now = time.time()
    last = user_last_used.get(uid, 0)

    if now - last < COOLDOWN:
        return False

    user_last_used[uid] = now
    return True

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 FREE Downloader Bot\n\n"
        "📥 Send video link\n"
        "⚠ Max 2 downloads per user\n"
        "🎞 Max quality: 720p\n\n"
        "Commands:\n"
        "/search song"
    )

# ================= SEARCH =================
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)

    if not query:
        return await update.message.reply_text("Usage: /search song")

    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        data = ydl.extract_info(f"ytsearch5:{query}", download=False)

    msg = "🔍 Top Results:\n\n"
    for i, v in enumerate(data["entries"], 1):
        msg += f"{i}. {v['title']}\n{v['webpage_url']}\n\n"

    await update.message.reply_text(msg)

# ================= ASK FORMAT =================
async def ask_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    url = update.message.text.strip()

    if not is_valid_url(url):
        return await update.message.reply_text("❌ Invalid link")

    if not check_limit(uid):
        return await update.message.reply_text("❌ Limit reached (2 downloads max)")

    if not check_cooldown(uid):
        return await update.message.reply_text("⏳ Please wait before next request")

    keyboard = [
        [
            InlineKeyboardButton("🎬 MP4", callback_data=f"mp4|{url}"),
            InlineKeyboardButton("🎵 MP3", callback_data=f"mp3|{url}")
        ]
    ]

    await update.message.reply_text(
        "Select format:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= PROCESS =================
async def process_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.message.chat.id
    fmt, url = query.data.split("|")

    os.makedirs(DOWNLOAD_PATH, exist_ok=True)

    await query.message.reply_text("⏳ Processing...")

    try:
        # ===== VIDEO INFO =====
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title")
        thumb = info.get("thumbnail")
        duration = info.get("duration", 0)
        uploader = info.get("uploader", "Unknown")
        size = info.get("filesize_approx")

        size_text = f"{round(size/1024/1024,2)} MB" if size else "Unknown"

        await context.bot.send_photo(
            uid,
            photo=thumb,
            caption=(
                f"🎬 {title}\n"
                f"📺 {uploader}\n"
                f"⏱ {duration//60}:{duration%60:02d}\n"
                f"📦 {size_text}"
            )
        )

        # ===== DOWNLOAD SETTINGS =====
        if fmt == "mp3":
            ydl_opts = {
                "format": "bestaudio",
                "outtmpl": f"{DOWNLOAD_PATH}/%(title).50s.%(ext)s",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3"
                }],
                "noplaylist": True
            }
        else:
            ydl_opts = {
                "format": "best[height<=720]",
                "outtmpl": f"{DOWNLOAD_PATH}/%(title).50s.%(ext)s",
                "continuedl": True,
                "noplaylist": True
            }

        # ===== DOWNLOAD =====
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        file = sorted(os.listdir(DOWNLOAD_PATH))[-1]
        path = os.path.join(DOWNLOAD_PATH, file)

        await context.bot.send_document(uid, open(path, "rb"))

        os.remove(path)
        increase_limit(uid)

    except Exception as e:
        await context.bot.send_message(uid, "❌ Download failed")

# ================= APP =================
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("search", search))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ask_format))
app.add_handler(CallbackQueryHandler(process_download))

print("🚀 FREE BOT RUNNING...")
app.run_polling()
