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
        # بدون نیاز به ffmpeg
        "format": "best[ext=mp4]/best",

        "outtmpl": output_template,

        "noplaylist": True,

        "quiet": True,
        "no_warnings": True,

        "http_headers": {
            "User-Agent":
                "Mozilla/5.0 (Android 12; Mobile)"
        },
    }

    with YoutubeDL(options) as ydl:

        info = ydl.extract_info(
            url,
            download=True
        )

        filename = ydl.prepare_filename(info)

        file_path = Path(filename)

        if file_path.exists():
            return str(file_path)

        mp4_file = file_path.with_suffix(".mp4")

        if mp4_file.exists():
            return str(mp4_file)

        raise Exception(
            "Video file was not created"
        )


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ALLOWED_USER_ID:
        return

    await update.message.reply_text(
        "لینک ویدئوی X/Twitter را بفرست."
    )


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ALLOWED_USER_ID:
        return


    url = extract_x_url(
        update.message.text or ""
    )


    if not url:

        await update.message.reply_text(
            "فقط لینک X/Twitter بفرست."
        )

        return


    status = await update.message.reply_text(
        "⏳ در حال دانلود..."
    )


    with tempfile.TemporaryDirectory() as temp_dir:

        try:

            video_path = await asyncio.to_thread(
                download_video,
                url,
                temp_dir
            )


            await status.edit_text(
                "📤 در حال ارسال..."
            )


            with open(
                video_path,
                "rb"
            ) as video:

                await update.message.reply_video(
                    video=video,
                    supports_streaming=True
                )


            await status.delete()


        except Exception as e:

            print(
                "DOWNLOAD ERROR:",
                repr(e)
            )


            await status.edit_text(
                "❌ دانلود ویدئو ناموفق بود."
            )



def main():

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )


    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )


    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )


    print(
        "Bot is running..."
    )


    app.run_polling()



if __name__ == "__main__":
    main()
