import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# تابع شروع
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! لطفاً لینک محصول آمازون رو بفرستید.\n(اگر لینک EU باشه، خودکار به AE تبدیل میشه)"
    )

# تابع دریافت پیام
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    # بررسی لینک معتبر آمازون
    if "amazon." not in url:
        await update.message.reply_text("⚠️ لطفاً یک لینک معتبر از آمازون بفرستید.")
        return

    # تبدیل لینک EU به AE
    url = url.replace("amazon.eu", "amazon.ae")

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        r = requests.get(url, headers=headers)
        soup = BeautifulSoup(r.content, "html.parser")

        # گرفتن قیمت محصول
        price_tag = soup.find("td", class_="text-left")
        price = price_tag.text.strip() if price_tag else "قیمت پیدا نشد"

        await update.message.reply_text(f"لینک اصلاح شده: {url}\nقیمت: {price} AED")
    except Exception as e:
        await update.message.reply_text(f"خطا در دریافت اطلاعات محصول: {e}")

# اجرای برنامه
if __name__ == "__main__":
    TOKEN = "YOUR_BOT_TOKEN_HERE"  # توکن خودت رو اینجا بزار

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()
