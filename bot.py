import os
import re
import asyncio
import tempfile
import urllib.request
import json

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ALLOWED_USER_ID = 1337113228


def extract_x_url(text):
    pattern = r"https?://(?:www\.)?(?:x\.com|twitter\.com)/[^\s]+"
    match = re.search(pattern, text)
    return match.group(0) if match else None


def download_video_via_api(url, output_path):
    # استفاده از API رایگان cobalt برای دریافت مستقیم لینک فایل mp4
    api_url = "https://api.cobalt.tools/api/json"
    payload = json.dumps({"url": url}).encode("utf-8")
    
    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0"
        },
        method="POST"
    )
    
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        
    if data.get("status") in ["stream", "redirect"]:
        download_url = data["url"]
    else:
        raise Exception(f"Cobalt API error: {data}")

    # دانلود خود فایل MP4 و ذخیره در پوشه موقت
    urllib.request.urlretrieve(download_url, output_path)
    return output_path


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
            video_path = os.path.join(temp_dir, "video.mp4")
            
            await asyncio.to_thread(
                download_video_via_api,
                url,
                video_path
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
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
