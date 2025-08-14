import os
import httpx
from lxml import html
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AED_TO_IRR = float(os.getenv("AED_TO_IRR_MANUAL", "150000"))
SHIPPING_FLAT_AED = float(os.getenv("SHIPPING_FLAT_AED", "15"))
CUSTOMS_PERCENT = float(os.getenv("CUSTOMS_PERCENT", "8"))
SERVICE_FEE_PERCENT = float(os.getenv("SERVICE_FEE_PERCENT", "5"))
EXTRA_FIXED_IRR = float(os.getenv("EXTRA_FIXED_IRR", "0"))
AS_TOMAN = os.getenv("AS_TOMAN", "false").lower() == "true"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! لینک محصول آمازون دبی رو بفرست تا قیمت نهایی رو بگم.")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if "amazon.ae" not in url:
        await update.message.reply_text("لطفاً فقط لینک آمازون دبی رو بفرست.")
        return

    try:
        r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"})
        tree = html.fromstring(r.content)
        price_el = tree.xpath('//span[@class="a-price-whole"]/text()')
        if not price_el:
            await update.message.reply_text("قیمت پیدا نشد. شاید ساختار صفحه تغییر کرده.")
            return
        
        price_aed = float(price_el[0].replace(",", "").strip())
        total_aed = price_aed + SHIPPING_FLAT_AED
        total_aed += total_aed * (CUSTOMS_PERCENT / 100)
        total_aed += total_aed * (SERVICE_FEE_PERCENT / 100)
        
        total_irr = total_aed * AED_TO_IRR + EXTRA_FIXED_IRR
        if AS_TOMAN:
            total_irr = total_irr / 10

        await update.message.reply_text(f"💰 قیمت نهایی: {total_irr:,.0f} {'تومان' if AS_TOMAN else 'ریال'}")

    except Exception as e:
        await update.message.reply_text(f"خطا در پردازش: {e}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.run_polling()
