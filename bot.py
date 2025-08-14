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
AED_TO_IRR_MANUAL = 150000  # اگر نرخ سایت خراب بود، این مقدار استفاده می‌شود

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام 😎\n"
        "میخوای بدونی قیمت محصول آمازون دبی چنده و هزینه‌هاش چطور میشه؟\n"
        "فقط لینک محصول رو برام بفرست تا برات همه چیز رو حساب کنم 💰📦"
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
                "اوپس 😅، قیمت محصول پیدا نشد! مطمئن شو لینک آمازون دبی است و دوباره امتحان کن."
            )
            return

        price_aed = float(price_el[0].replace(",", "").strip())
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطا در گرفتن قیمت: {e}")
        return

    # گرفتن نرخ درهم از TGJU (لحظه‌ای)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://www.tgju.org/profile/price_aed")
            tree = html.fromstring(resp.text)
        
        rate_el = tree.xpath('//td[@class="text-left"]/text()')
        if not rate_el or rate_el[0].strip() == '':
            rate = AED_TO_IRR_MANUAL
        else:
            rate = float(rate_el[0].replace(",", "").strip())
    except:
        rate = AED_TO_IRR_MANUAL

    # محاسبه هزینه‌ها
    shipping_aed = SHIPPING_FLAT_AED
    customs_fee = (price_aed + shipping_aed) * CUSTOMS_PERCENT / 100
    service_fee = (price_aed + shipping_aed) * SERVICE_FEE_PERCENT / 100
    total_aed = price_aed + shipping_aed + customs_fee + service_fee
    total_irr = total_aed * rate

    # ارسال پیام جزئیات
    message = (
        f"💱 نرخ درهم (لحظه‌ای): {rate:,} ریال\n"
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
