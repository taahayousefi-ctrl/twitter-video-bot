import os
import re
import asyncio
import tempfile

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from yt_dlp import YoutubeDL


BOT_TOKEN = os.environ["BOT_TOKEN"]

ALLOWED_USER_ID = 1337113228


def extract_x_url(text):
    pattern = r"https?://(?:www\.)?(?:x\.com|twitter\.com)/[^\s]+"
    match = re.search(pattern, text)
    return match.group(0) if match else None


def download_video(url, output_dir):

    output_template = os.path.join(
        output_dir,
        "%(id)s.%(ext)s"
    )

    options = {
        # فقط یک فرمت تکی (muxed) انتخاب می‌شود — هیچ merge انجام نمی‌شود
        "format": "best[ext=mp4]/best",

        # جلوگیری کامل از هرگونه merge و post-process
        "merge_output_format": None,
        "postprocessors": [],
        "noplaylist": True,

        "quiet": True,
        "no_warnings": True,

        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Android 12; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        },
    }

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

        if os.path.exists(filename):
            return filename

        # fallback اگر اسم فایل فرق کرده باشه
        for f in os.listdir(output_dir):
            path = os.path.join(output_dir, f)
            if os.path.isfile(path) and path.endswith((".mp4", ".mkv", ".webm")):
                return path

        raise Exception("Video file was not created")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    await update.message.reply_text("لینک X/Twitter را بفرست.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    url = extract_x_url(update.message.text or "")

    if not url:
        await update.message.reply_text("لینک معتبر X بفرست.")
        return

    status = await update.message.reply_text("⏳ در حال دانلود...")

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            video_path = await asyncio.to_thread(
                download_video,
                url,
                temp_dir
            )

            await status.edit_text("📤 در حال ارسال...")

            with open(video_path, "rb") as video:
                await update.message.reply_video(
                    video=video,
                    supports_streaming=True
                )

            await status.delete()

        except Exception as e:
            print("DOWNLOAD ERROR:", repr(e))
            await status.edit_text("❌ دانلود ناموفق بود.")


def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & \~filters.COMMAND, handle_message)
    )

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
