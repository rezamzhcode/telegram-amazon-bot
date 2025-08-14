import os
import re
import httpx
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# هزینه‌ها و کارمزد
SHIPPING_FLAT_AED = float(os.getenv("SHIPPING_FLAT_AED", 15))
CUSTOMS_PERCENT = float(os.getenv("CUSTOMS_PERCENT", 8))
SERVICE_FEE_PERCENT = float(os.getenv("SERVICE_FEE_PERCENT", 5))
EXTRA_FIXED_IRR = float(os.getenv("EXTRA_FIXED_IRR", 0))

# وزن ماکزیمم بدون اضافه‌بار و هزینه اضافه
MAX_WEIGHT_KG = 50
EXTRA_WEIGHT_COST_PER_50KG_IRR = 500  # ریال

# تابع گرفتن نرخ لحظه‌ای درهم از TGJU
async def get_aed_rate():
    url = "https://www.tgju.org/profile/price_aed"
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
    soup = BeautifulSoup(r.text, "lxml")
    td = soup.find("td", class_="text-left")
    if td:
        text = td.text.strip().replace(",", "")
        try:
            return float(text)
        except:
            return None
    return None

# تابع گرفتن قیمت و وزن محصول از لینک آمازون دبی
async def get_amazon_product(link):
    async with httpx.AsyncClient() as client:
        r = await client.get(link, headers={"User-Agent":"Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "lxml")

    # قیمت
    price_tag = soup.select_one("#corePriceDisplay_desktop_feature_div span.a-price-whole")
    if price_tag:
        price = float(price_tag.text.strip().replace(",", ""))
    else:
        price = None

    # وزن
    weight_tag = soup.find(text=re.compile(r"وزن|Weight", re.I))
    weight = 0
    if weight_tag:
        match = re.search(r"([\d,.]+)\s*(kg|g)", weight_tag, re.I)
        if match:
            w = float(match.group(1).replace(",", ""))
            if match.group(2).lower() == "g":
                w = w / 1000
            weight = w
    return price, weight

# محاسبه قیمت نهایی
def calculate_final_price(price_aed, rate_irr, weight):
    shipping = SHIPPING_FLAT_AED
    base_total_aed = price_aed + shipping
    customs = base_total_aed * (CUSTOMS_PERCENT / 100)
    service_fee = base_total_aed * (SERVICE_FEE_PERCENT / 100)
    total_aed = base_total_aed + customs + service_fee

    # اضافه بار
    extra_weight = max(0, weight - MAX_WEIGHT_KG)
    extra_cost = (extra_weight // 50 + (1 if extra_weight % 50 > 0 else 0)) * EXTRA_WEIGHT_COST_PER_50KG_IRR

    total_irr = total_aed * rate_irr + EXTRA_FIXED_IRR + extra_cost
    return total_irr, shipping, customs, service_fee, extra_cost

# هندلر شروع
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! لینک محصول آمازون دبی خودت رو بفرست تا قیمت نهایی به ریال برات حساب کنم."
    )

# هندلر پیام لینک
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    await update.message.reply_text("⏳ در حال دریافت اطلاعات محصول و نرخ درهم...")

    rate = await get_aed_rate()
    if not rate:
        await update.message.reply_text("⚠️ نرخ درهم پیدا نشد، لطفاً دوباره امتحان کنید.")
        return

    price_aed, weight = await get_amazon_product(link)
    if not price_aed:
        await update.message.reply_text("⚠️ قیمت محصول پیدا نشد! مطمئن شو لینک آمازون دبی است و دوباره امتحان کن.")
        return

    total_irr, shipping, customs, service_fee, extra_weight_cost = calculate_final_price(price_aed, rate, weight)

    msg = f"""💱 نرخ لحظه‌ای درهم: {rate:,.0f} ریال
🛒 قیمت محصول: {price_aed} AED
📦 هزینه ارسال: {shipping} AED
⚖️ وزن محصول: {weight:.2f} کیلوگرم
🛃 گمرک: {customs:,.0f} ریال
💵 کارمزد: {service_fee:,.0f} ریال
💰 اضافه‌بار: {extra_weight_cost:,.0f} ریال
🏁 قیمت تقریبی به ریال: {total_irr:,.0f} ریال
"""
    await update.message.reply_text(msg)

# main
app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()
