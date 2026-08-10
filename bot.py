import os
import re
import asyncio
import tempfile
from pathlib import Path

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


def extract_video_url(text):
    pattern = r"https?://[^\s]+"
    match = re.search(pattern, text)
    return match.group(0) if match else None


def download_video(url, output_dir):
    output_template = os.path.join(
        output_dir,
        "%(id)s.%(ext)s"
    )

    options = {
        "format": "bestvideo*+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

        mp4_file = Path(filename).with_suffix(".mp4")

        if mp4_file.exists():
            return str(mp4_file)

        return filename


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    await update.message.reply_text(
        "لینک ویدئو از X، YouTube یا Instagram را بفرست."
    )


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    url = extract_video_url(
        update.message.text or ""
    )

    if not url:
        await update.message.reply_text(
            "یک لینک ویدئوی معتبر بفرست."
        )
        return

    message = await update.message.reply_text(
        "⏳ در حال دانلود..."
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            video_path = await asyncio.to_thread(
                download_video,
                url,
                temp_dir,
            )

            if not os.path.exists(video_path):
                raise Exception(
                    "Video file was not created"
                )

            await message.edit_text(
                "📤 در حال ارسال ویدئو..."
            )

            with open(video_path, "rb") as video:
                await update.message.reply_video(
                    video=video,
                    supports_streaming=True,
                )

            await message.delete()

        except Exception as e:
            print("ERROR:", e)

            await message.edit_text(
                "❌ نتونستم ویدئو رو دانلود کنم."
            )


def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
