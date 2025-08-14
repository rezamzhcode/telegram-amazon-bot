# bot.py
import os
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# توکن جدیدت رو اینجا بذار
BOT_TOKEN = "8259083093:AAEY2dpAm0uPo27x49Ee81QidTEGNJmEVNo"

# تبدیل لینک EU به AE
def convert_link(url: str) -> str:
    if ".eu/" in url:
        url = url.replace(".eu/", ".ae/")
    return url

# گرفتن قیمت لحظه‌ای
def get_price(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/115.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return "خطا در دریافت صفحه."
    soup = BeautifulSoup(response.text, "html.parser")
    price_td = soup.find("td", class_="text-left")
    if price_td:
        return price_td.text.strip()
    return "قیمت پیدا نشد."

# فرمان استارت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! لینک آمازون ارسال کنید تا قیمت بگیرم.")

# دریافت پیام کاربر
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if "amazon" not in url:
        await update.message.reply_text("⚠️ لطفاً یک لینک معتبر از آمازون بفرست.")
        return

    url = convert_link(url)
    price = get_price(url)
    await update.message.reply_text(f"قیمت لحظه‌ای: {price}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()
