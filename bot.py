import os
import re
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# تنظیمات هزینه‌ها
SHIPPING_AED = 15
CUSTOMS_PERCENT = 10
SERVICE_PERCENT = 10
OVERWEIGHT_LIMIT = 50  # کیلو
OVERWEIGHT_FEE_TOMAN = 500_000  # 500 هزار تومن به ازای هر 50 کیلو اضافه

# گرفتن نرخ لحظه‌ای درهم از TGJU
async def get_aed_rate():
    url = "https://www.tgju.org/profile/price_aed"
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
    soup = BeautifulSoup(r.text, "lxml")
    price_td = soup.find("td", class_="text-left")
    if not price_td:
        return None
    rial_price = float(price_td.text.replace(",", "").strip())
    return rial_price / 10  # تبدیل به تومان

# گرفتن قیمت و وزن محصول از آمازون
async def get_product_info(link):
    # تبدیل amazon.eu به amazon.ae
    link = re.sub(r"amazon\.[a-z]{2,3}", "amazon.ae", link)

    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient() as client:
        r = await client.get(link, headers=headers)
    soup = BeautifulSoup(r.text, "lxml")

    # پیدا کردن قیمت
    price_tag = soup.select_one(".a-price .a-offscreen")
    if not price_tag:
        return None, None
    price_aed = float(price_tag.text.replace("AED", "").replace(",", "").strip())

    # پیدا کردن وزن
    text_content = soup.get_text(" ", strip=True)
    weight_match = re.search(r"(\d+(?:\.\d+)?)\s?(kg|g|pounds|lb)", text_content, re.IGNORECASE)
    weight_kg = None
    if weight_match:
        value, unit = weight_match.groups()
        value = float(value)
        unit = unit.lower()
        if unit == "g":
            weight_kg = value / 1000
        elif unit in ["pounds", "lb"]:
            weight_kg = value * 0.453592
        else:
            weight_kg = value

    return price_aed, weight_kg

# شروع ربات
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام 👋\n"
        "لینک محصول آمازون دبی رو بفرست تا قیمت رو به تومان و با همه هزینه‌ها حساب کنم 📦💰"
    )

# پردازش لینک
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    if "amazon" not in link:
        await update.message.reply_text("⚠️ لطفاً یک لینک معتبر از آمازون بفرست.")
        return

    aed_rate = await get_aed_rate()
    if not aed_rate:
        await update.message.reply_text("❌ نتونستم نرخ درهم رو بگیرم. دوباره تلاش کن.")
        return

    price_aed, weight_kg = await get_product_info(link)
    if price_aed is None:
        await update.message.reply_text("❌ نتونستم قیمت محصول رو پیدا کنم.")
        return

    # محاسبه هزینه‌ها
    shipping_cost_toman = SHIPPING_AED * aed_rate
    customs_cost = (CUSTOMS_PERCENT / 100) * (price_aed * aed_rate)
    service_fee = (SERVICE_PERCENT / 100) * (price_aed * aed_rate)

    overweight_fee = 0
    if weight_kg and weight_kg > OVERWEIGHT_LIMIT:
        extra_units = (weight_kg - OVERWEIGHT_LIMIT) // OVERWEIGHT_LIMIT + 1
        overweight_fee = extra_units * OVERWEIGHT_FEE_TOMAN

    final_price_toman = (price_aed * aed_rate) + shipping_cost_toman + customs_cost + service_fee + overweight_fee

    # ساخت پیام خروجی
    msg = (
        f"💱 نرخ لحظه‌ای درهم: {aed_rate:,.0f} تومان\n"
        f"🛒 قیمت کالا: {price_aed} AED\n"
        f"⚖️ وزن کالا: {weight_kg:.2f} کیلوگرم" if weight_kg else "⚖️ وزن کالا: نامشخص"
    )
    msg += (
        f"\n📦 هزینه ارسال: {shipping_cost_toman:,.0f} تومان"
        f"\n🛃 گمرک ({CUSTOMS_PERCENT}%): {customs_cost:,.0f} تومان"
        f"\n💰 کارمزد ({SERVICE_PERCENT}%): {service_fee:,.0f} تومان"
        f"\n📦 اضافه بار: {overweight_fee:,.0f} تومان"
        f"\n🏁 قیمت نهایی تقریبی: {final_price_toman:,.0f} تومان"
    )

    await update.message.reply_text(msg)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.run_polling()
