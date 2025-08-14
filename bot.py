import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import httpx
from lxml import html
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# ثابت‌ها برای محاسبه ریال
SHIPPING_FLAT_AED = 15
CUSTOMS_PERCENT = 8
SERVICE_FEE_PERCENT = 5
AED_TO_IRR_MANUAL = 150000  # نرخ دستی درهم به ریال

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! لینک محصول آمازون دبی را ارسال کنید تا قیمتش به ریال محاسبه شود."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    # گرفتن قیمت محصول از آمازون
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            tree = html.fromstring(resp.text)

        price_el = tree.xpath('//span[@class="a-price-whole"]/text()')
        if not price_el or price_el[0].strip() == '':
            await update.message.reply_text(
                "⚠️ قیمت محصول پیدا نشد. لطفاً مطمئن شوید لینک آمازون دبی است."
            )
            return

        price_aed = float(price_el[0].replace(",", "").strip())
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطا در گرفتن قیمت: {e}")
        return

   # محاسبه هزینه‌ها
shipping_aed = SHIPPING_FLAT_AED
customs_fee = (price_aed + shipping_aed) * CUSTOMS_PERCENT / 100
service_fee = (price_aed + shipping_aed) * SERVICE_FEE_PERCENT / 100

total_aed = price_aed + shipping_aed + customs_fee + service_fee
total_irr = total_aed * rate

# ارسال پیام جزئیات
message = (
    f"💱 نرخ درهم: {rate:,} ریال\n"
    f"🛒 قیمت کالا: {price_aed} AED\n"
    f"📦 هزینه ارسال: {shipping_aed} AED\n"
    f"💰 درصد کارمزد: {SERVICE_FEE_PERCENT}%\n"
    f"🛃 گمرک: {CUSTOMS_PERCENT}%\n"
    f"🏁 قیمت تقریبی به ریال: {int(total_irr):,} ریال"
)

await update.message.reply_text(message)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot is running...")
    app.run_polling()
