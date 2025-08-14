import os
import re
import asyncio
import httpx
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AED_TO_IRR_MANUAL = float(os.getenv("AED_TO_IRR_MANUAL", "150000"))

SHIPPING_FLAT_AED = float(os.getenv("SHIPPING_FLAT_AED", 15))
CUSTOMS_PERCENT = float(os.getenv("CUSTOMS_PERCENT", 10))
SERVICE_FEE_PERCENT = float(os.getenv("SERVICE_FEE_PERCENT", 10))
EXTRA_FIXED_IRR = float(os.getenv("EXTRA_FIXED_IRR", 0))
OVERWEIGHT_THRESHOLD_KG = 50
OVERWEIGHT_FEE_PER_50KG = 500_000  # تومان

async def get_aed_rate():
    url = "https://www.tgju.org/profile/price_aed"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
        soup = BeautifulSoup(r.text, "lxml")
        try:
            price_text = soup.find("td", class_="text-left").text.strip().replace(",", "")
            return float(price_text)
        except:
            return AED_TO_IRR_MANUAL

def extract_kg(text):
    match = re.search(r"([\d,.]+)\s*kg", text, re.IGNORECASE)
    if match:
        return float(match.group(1).replace(",", ""))
    return None

def convert_eu_to_ae(link):
    return link.replace(".eu/", ".ae/")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    # تبدیل لینک EU به AE
    link = convert_eu_to_ae(text)
    
    # دریافت قیمت صفحه آمازون
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(link, headers={"User-Agent": "Mozilla/5.0"})
        except:
            await update.message.reply_text("⚠️ خطا در دریافت لینک، دوباره تلاش کن.")
            return
    
    soup = BeautifulSoup(r.text, "lxml")
    
    # قیمت کالا
    price_tag = soup.select_one("#corePrice_feature_div span.a-price-whole")
    if not price_tag:
        await update.message.reply_text("⚠️ لطفاً یک لینک معتبر از آمازون بفرست.")
        return
    try:
        price_aed = float(price_tag.text.strip().replace(",", "").replace(".", ""))
    except:
        await update.message.reply_text("⚠️ خطا در خواندن قیمت محصول.")
        return
    
    # وزن کالا
    weight_text = soup.find(string=re.compile(r"kg", re.IGNORECASE))
    weight_kg = extract_kg(weight_text) if weight_text else 0

    # محاسبه اضافه‌بار
    overweight_fee = 0
    if weight_kg > OVERWEIGHT_THRESHOLD_KG:
        extra_units = (weight_kg - OVERWEIGHT_THRESHOLD_KG) / 50
        overweight_fee = int(extra_units * OVERWEIGHT_FEE_PER_50KG)

    # نرخ لحظه‌ای درهم
    aed_rate = await get_aed_rate()
    # تبدیل به تومان
    aed_rate_toman = aed_rate / 10

    shipping_toman = SHIPPING_FLAT_AED * aed_rate_toman
    customs_toman = price_aed * aed_rate_toman * CUSTOMS_PERCENT / 100
    service_fee_toman = price_aed * aed_rate_toman * SERVICE_FEE_PERCENT / 100

    total_price_toman = int(price_aed * aed_rate_toman + shipping_toman + customs_toman + service_fee_toman + overweight_fee + EXTRA_FIXED_IRR)

    msg = (
        f"💱 نرخ لحظه‌ای درهم: {aed_rate_toman:,.0f} تومان\n"
        f"🛒 قیمت کالا: {price_aed} AED\n"
        f"📦 هزینه ارسال: {SHIPPING_FLAT_AED} AED ({shipping_toman:,.0f} تومان)\n"
        f"🛃 گمرک: {CUSTOMS_PERCENT}% ({customs_toman:,.0f} تومان)\n"
        f"💵 درصد کارمزد: {SERVICE_FEE_PERCENT}% ({service_fee_toman:,.0f} تومان)\n"
        f"⚖️ وزن کالا: {weight_kg} kg (اضافه بار: {overweight_fee:,.0f} تومان)\n"
        f"🏁 قیمت نهایی: {total_price_toman:,.0f} تومان"
    )
    await update.message.reply_text(msg)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! لینک آمازون دبی یا EU خود را بفرست تا قیمت نهایی را محاسبه کنم.")

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

if __name__ == "__main__":
    print("Bot started...")
    app.run_polling()
