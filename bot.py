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
        # فقط فرمت آماده، بدون merge
        "format": "http-832/http-256/best[ext=mp4][vcodec!=none][acodec!=none]",

        "outtmpl": output_template,

        "noplaylist": True,

        "quiet": True,
        "no_warnings": True,

        # جلوگیری کامل از post process
        "postprocessors": [],

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


        if os.path.exists(filename):
            return filename


        for f in os.listdir(output_dir):

            path = os.path.join(
                output_dir,
                f
            )

            if os.path.isfile(path):
                return path


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
        "لینک X/Twitter را بفرست."
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
            "لینک معتبر X بفرست."
        )

        return


    status =
