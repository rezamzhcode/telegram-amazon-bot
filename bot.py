import os
import httpx
from lxml import html
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TGJU_URL = "https://www.tgju.org/profile/price_aed"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! لینک محصول آمازون دبی رو بفرست تا قیمت نهایی رو بگم.")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if "amazon.ae" not in url:
        await update.message.reply_text("لطفاً فقط لینک آمازون دبی رو بفرست.")
        return

    try:
        # گرفتن قیمت محصول از آمازون
        r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"})
        tree = html.fromstring(r.content)
        price_el = tree.xpath('//span[@class="a-price-whole"]/text()')
        if not price_el:
            await update.message.reply_text("قیمت پیدا نشد. شاید ساختار صفحه تغییر کرده.")
            return
        price_aed = float(price_el[0].replace(",", "").strip())

        # گرفتن نرخ لحظه‌ای درهم به ریال
        r = httpx.get(TGJU_URL)
        tree = html.fromstring(r.content)
        rate_el = tree.xpath('//span[@class="value"]/text()')
        if not rate_el:
            await update.message.reply_text("نرخ تبدیل یافت نشد.")
            return
        rate = float(rate_el[0].replace(",", "").strip())

        total_irr = price_aed * rate
        await update.message.reply_text(f"💰 قیمت نهایی: {total_irr:,.0f} ریال")

    except Exception as e:
        await update.message.reply_text(f"خطا در پردازش: {e}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.run_polling()
