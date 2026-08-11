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

BOT_TOKEN = os.environ["8989302687:AAGaoLyFtgGrNpS0EnUi3EnSzYvCvftV6Qw"]
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
    # فقط یک فایل آماده؛ بدون نیاز به ffmpeg
    "format": "best[ext=mp4]/best",

    "outtmpl": output_template,
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,

    # جلوگیری از هرگونه merge
    "merge_output_format": None,
}

with YoutubeDL(options) as ydl:
    info = ydl.extract_info(
        url,
        download=True
    )

    filename = ydl.prepare_filename(info)

    # اگر خروجی mp4 بود
    if os.path.exists(filename):
        return filename

    # پیدا کردن فایل واقعی ایجادشده
    base = Path(filename).stem

    for file in Path(output_dir).glob(
        f"{base}.*"
    ):
        if file.is_file():
            return str(file)

    raise Exception(
        "Video file was not created"
    )

def get_tunelio_link(url):
if not TUNELIO_API_KEY:
raise Exception(
"TUNELIO_API_KEY is not configured"
)

response = requests.get(
    "https://tunelio.dev/create",
    params={
        "quality": "480p",
        "url": url,
    },
    headers={
        "Authorization":
            f"Bearer {TUNELIO_API_KEY}",
    },
    timeout=60,
)

if response.status_code in (
    401,
    403,
    429,
):
    raise RuntimeError(
        "TUNELIO_LIMIT"
    )

response.raise_for_status()

data = response.json()

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
        raise RuntimeError(
            "TUNELIO_LIMIT"
        )

    raise RuntimeError(
        data.get("message")
        or data.get("error")
        or "Tunelio error"
    )

tunnel_url = data.get("url")

if not tunnel_url:
    raise RuntimeError(
        "Tunelio did not return a download link"
    )

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

async def safe_edit(message, text):
try:
await message.edit_text(text)
return True
except Exception as e:
print(
"TELEGRAM EDIT ERROR:",
repr(e)
)
return False

async def start(
update: Update,
context: ContextTypes.DEFAULT_TYPE
):
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
        await safe_edit(
            message,
            "⏳ در حال آماده‌سازی لینک YouTube..."
        )

        result = await asyncio.to_thread(
            get_tunelio_link,
            url,
        )

        filename = result["filename"]
        tunnel_url = result["url"]

        await safe_edit(
            message,
            f"✅ آماده شد\n\n"
            f"🎬 {filename}\n"
            f"📺 کیفیت: {result['quality']}\n\n"
            f"🔗 لینک دانلود:\n{tunnel_url}"
        )

    except RuntimeError as e:

        if str(e) == "TUNELIO_LIMIT":
            await safe_edit(
                message,
                "❌ اعتبار سرویس YouTube تمام شده.\n\n"
                "🔑 یک کلید جدید Tunelio بگیر و "
                "متغیر TUNELIO_API_KEY را با کلید جدید تنظیم کن."
            )

        else:
            print(
                "TUNELIO ERROR:",
                repr(e)
            )

            await safe_edit(
                message,
                "❌ سرویس YouTube نتونست لینک دانلود بسازه."
            )

    except Exception as e:

        print(
            "TUNELIO ERROR:",
            repr(e)
        )

        await safe_edit(
            message,
            "❌ در دریافت لینک YouTube مشکلی پیش آمد."
        )

    return

# -----------------------------
# X / Instagram → yt-dlp
# -----------------------------

await safe_edit(
    message,
    "⏳ در حال دانلود..."
)

with tempfile.TemporaryDirectory() as temp_dir:

    try:

        video_path = await asyncio.to_thread(
            download_video,
            url,
            temp_dir,
        )

        if not os.path.exists(
            video_path
        ):
            raise Exception(
                "Video file was not created"
            )

        await safe_edit(
            message,
            "📤 در حال ارسال ویدئو..."
        )

        with open(
            video_path,
            "rb"
        ) as video:

            await update.message.reply_video(
                video=video,
                supports_streaming=True,
            )

        try:
            await message.delete()
        except Exception:
            pass

    except Exception as e:

        print(
            "DOWNLOAD ERROR:",
            repr(e)
        )

        await safe_edit(
            message,
            "❌ نتونستم ویدئو رو دانلود کنم."
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
        handle_message,
    )
)

print(
    "Bot is running..."
)

app.run_polling()

if name == "main":
main()
