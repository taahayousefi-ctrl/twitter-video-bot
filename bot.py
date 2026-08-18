import asyncio
import os
import re
import json
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from yt_dlp import YoutubeDL

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
TUNELIO_API_KEY = os.environ.get("TUNELIO_API_KEY")

ALLOWED_USER_ID = 1337113228
MAX_TELEGRAM_UPLOAD_BYTES = 49 * 1024 * 1024


def extract_video_url(text):
    pattern = r"https?://[^\s]+"
    match = re.search(pattern, text)
    if not match:
        return None

    return match.group(0).rstrip(".,؛،)]}")


def is_youtube_url(url):
    host = urlparse(url).netloc.lower().split(":", 1)[0]
    return (
        host == "youtu.be"
        or host == "youtube.com"
        or host.endswith(".youtube.com")
    )


def download_video(url, output_dir):
    output_template = os.path.join(output_dir, "%(id)s.%(ext)s")

    options = {
        # Prefer a Telegram-friendly MP4 under 50 MB.  If that exact
        # combination is unavailable, fall back to the best single file so
        # ffmpeg is not required in the deployment environment.
        "format": (
            "best[ext=mp4][filesize<49M]/"
            "best[ext=mp4][filesize_approx<49M]/"
            "best[filesize<49M]/"
            "best[filesize_approx<49M]/"
            "best[ext=mp4]/best"
        ),
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
        "postprocessors": [],
        "restrictfilenames": True,
    }

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    if os.path.exists(filename):
        return filename

    video_id = info.get("id")
    if video_id:
        for file in Path(output_dir).glob(f"{video_id}.*"):
            if file.is_file():
                return str(file)

    for file in Path(output_dir).iterdir():
        if file.is_file():
            return str(file)

    raise FileNotFoundError("Video file was not created")


def get_tunelio_link(url):
    if not TUNELIO_API_KEY:
        raise RuntimeError("TUNELIO_LIMIT")

    query = urlencode({"quality": "480p", "url": url})
    request = Request(
        f"https://tunelio.dev/create?{query}",
        headers={"Authorization": f"Bearer {TUNELIO_API_KEY}"},
    )

    try:
        with urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        if e.code in (401, 403, 429):
            raise RuntimeError("TUNELIO_LIMIT") from e
        raise

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
            data.get("message") or data.get("error") or "Tunelio error"
        )

    tunnel_url = data.get("url")
    if not tunnel_url:
        raise RuntimeError("Tunelio did not return a download link")

    return {
        "url": tunnel_url,
        "filename": data.get("filename", "youtube_video.mp4"),
        "quality": data.get("quality", "480p"),
    }


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    await update.message.reply_text(
        "لینک ویدئو از X، YouTube یا Instagram را بفرست."
    )


async def send_downloaded_video(update, message, url):
    await message.edit_text("⏳ در حال دانلود...")

    with tempfile.TemporaryDirectory() as temp_dir:
        video_path = await asyncio.to_thread(download_video, url, temp_dir)

        if not os.path.exists(video_path):
            raise FileNotFoundError("Video file was not created")

        file_size = os.path.getsize(video_path)
        if file_size > MAX_TELEGRAM_UPLOAD_BYTES:
            raise RuntimeError("FILE_TOO_LARGE")

        await message.edit_text("📤 در حال ارسال ویدئو...")

        with open(video_path, "rb") as video:
            await update.message.reply_video(
                video=video,
                supports_streaming=True,
                read_timeout=120,
                write_timeout=120,
                connect_timeout=120,
                pool_timeout=120,
            )

    await message.delete()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    url = extract_video_url(update.message.text or "")
    if not url:
        await update.message.reply_text("یک لینک ویدئوی معتبر بفرست.")
        return

    message = await update.message.reply_text("⏳ در حال بررسی لینک...")

    if is_youtube_url(url):
        try:
            await message.edit_text("⏳ در حال آماده‌سازی لینک YouTube...")
            result = await asyncio.to_thread(get_tunelio_link, url)

            await message.edit_text(
                f"✅ آماده شد\n\n"
                f"🎬 {result['filename']}\n"
                f"📺 کیفیت: {result['quality']}\n\n"
                f"🔗 لینک دانلود:\n{result['url']}"
            )
            return
        except RuntimeError as e:
            if str(e) != "TUNELIO_LIMIT":
                print("TUNELIO ERROR:", e)
            else:
                print("TUNELIO unavailable; falling back to yt-dlp")
        except Exception as e:
            print("TUNELIO ERROR:", repr(e))

    try:
        await send_downloaded_video(update, message, url)
    except RuntimeError as e:
        if str(e) == "FILE_TOO_LARGE":
            await message.edit_text(
                "❌ حجم ویدئو برای ارسال در تلگرام زیاد است."
            )
        else:
            print("DOWNLOAD ERROR:", repr(e))
            await message.edit_text("❌ نتونستم ویدئو رو دانلود کنم.")
    except Exception as e:
        print("DOWNLOAD ERROR:", repr(e))
        await message.edit_text("❌ نتونستم ویدئو رو دانلود کنم.")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
