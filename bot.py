import os
import re
import asyncio
import tempfile
from pathlib import Path

import requests
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
TUNELIO_API_KEY = os.environ.get("TUNELIO_API_KEY")

ALLOWED_USER_ID = 1337113228


def extract_video_url(text):
    pattern = r"https?://[^\s]+"
    match = re.search(pattern, text)
    return match.group(0) if match else None


def is_youtube_url(url):
    return (
        "youtube.com/" in url
        or "youtu.be/" in url
    )


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


def get_tunelio_link(url):
    if not TUNELIO_API_KEY:
        raise Exception("TUNELIO_API_KEY is not configured")

    response = requests.get(
        "https://tunelio.dev/create",
        params={
            "quality": "480p",
            "url": url,
        },
        headers={
            "Authorization": f"Bearer {TUNELIO_API_KEY}",
        },
        timeout=60,
    )

    # اعتبار تمام شده / کلید نامعتبر
    if response.status_code in (401, 403, 429):
        raise RuntimeError("TUNELIO_LIMIT")

    response.raise_for_status()

    data = response.json()

    # بعضی خطاها با status=200 برمی‌گردند
    if data.get("status") != "ok":
        error_text = str(data).lower()

        if any(
            x in error_text
            for x in (
                "limit",
                "quota",
                "credit",
                "rate",
                "unauthorized",
            )
        ):
            raise RuntimeError("TUNELIO_LIMIT")

        raise RuntimeError(
            data.get("message")
            or data.get("error")
            or "Tunelio error"
        )

    tunnel_url = data.get("url")

    if not tunnel_url:
        raise RuntimeError("Tunelio did not return a download link")

    return {
        "url": tunnel_url,
        "filename": data.get(
            "filename",
            "youtube_video.mp4"
        ),
        "quality": data.get(
            "quality",
            "480p"
        ),
    }


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
        "⏳ در حال بررسی لینک..."
    )

    # -----------------------------
    # YouTube → Tunelio
    # -----------------------------
    if is_youtube_url(url):
        try:
            await message.edit_text(
                "⏳ در حال آماده‌سازی لینک YouTube..."
            )

            result = await asyncio.to_thread(
                get_tunelio_link,
                url,
            )

            filename = result["filename"]
            tunnel_url = result["url"]

            await message.edit_text(
                f"✅ آماده شد\n\n"
                f"🎬 {filename}\n"
                f"📺 کیفیت: {result['quality']}\n\n"
                f"🔗 لینک دانلود:\n{tunnel_url}"
            )

        except RuntimeError as e:
            if str(e) == "TUNELIO_LIMIT":
                await message.edit_text(
                    "❌ اعتبار سرویس YouTube تمام شده.\n\n"
                    "🔑 یک کلید جدید Tunelio بگیر و "
                    "متغیر TUNELIO_API_KEY را با کلید جدید تنظیم کن."
                )
            else:
                print("TUNELIO ERROR:", e)

                await message.edit_text(
                    "❌ سرویس YouTube نتونست لینک دانلود بسازه."
                )

        except Exception as e:
            print("TUNELIO ERROR:", repr(e))

            await message.edit_text(
                "❌ در دریافت لینک YouTube مشکلی پیش آمد."
            )

        return

    # -----------------------------
    # X / Instagram → yt-dlp
    # -----------------------------
    await message.edit_text(
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
