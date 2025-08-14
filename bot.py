import os
import re
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

AED_SOURCE_URL = "https://www.tgju.org/profile/price_aed"

# --- گرفتن نرخ لحظه‌ای درهم ---
async def get_aed_price():
    async with httpx.AsyncClient() as client:
        r = await client.get(AED_SOURCE_URL)
        soup = BeautifulSoup(r.text, "lxml")
        price_el = soup.select_one("td.text-left")
        if price_el:
            price_str = price_el.text.strip().replace(",", "")
            return float(price_str)
    return None

# --- گرفتن قیمت و وزن محصول از آمازون ---
async def get_amazon_info(url):
    # تبدیل دامنه به amazon.ae
    url = re.sub(r"amazon\.(eu|com)", "amazon.ae", url)

    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
        r = await client.get(url, follow_redirects=True)
        soup = BeautifulSoup(r.text, "lxml")

        # قیمت محصول
        price_el = soup.select_one(".a-price .a-offscreen")
        price = None
        if price_el:
            price_str = price_el.text.strip().replace("AED", "").replace(",", "").strip()
            try:
                price = float(price_str)
            except:
                pass

        # وزن محصول
        weight = None
        # بخش مشخصات محصول
        for row in soup.select("table tr"):
            header = row.select_one("th")
            cell = row.select_one("td")
            if header and cell and "weight" in header.text.lower():
                weight_str = cell.text.strip().lower()
                weight = parse_weight(weight_str)
                break

        return price, weight

# --- تبدیل متن وزن به کیلوگرم ---
def parse_weight(weight_str):
    match = re.search(r"([\d\.]+)\s*(kg|g)", weight_str)
    if match:
        value = float(match.group(1))
        unit = match.group(2)
        if unit == "g":
            value = value / 1000
        return value
    return None

# --- محاسبه هزینه ---
def calculate_total(price_aed, aed_to_irr, weight_kg):
    shipping_aed = 15  # هزینه ثابت ارسال
    customs_percent = 8
    service_fee_percent = 5

    # اضافه بار
    extra_charge_irr = 0
    if weight_kg and weight_kg > 50:
        extra_kg = weight_kg - 50
        extra_blocks = int(extra_kg // 50) + (1 if extra_kg % 50 > 0 else 0)
        extra_charge_irr = extra_blocks * 500_000  # 500 هزار تومان به ازای هر 50 کیلو

    subtotal_aed = price_aed + shipping_aed
    subtotal_aed += subtotal_aed * customs_percent / 100
    subtotal_aed += subtotal_aed * service_fee_percent / 100

    total_irr = subtotal_aed * aed_to_irr + extra_charge_irr
    return total_irr, extra_charge_irr

# --- هندلر استارت ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام 👋\nلینک محصول آمازون دبی رو بفرست تا قیمت و هزینه نهایی رو برات حساب کنم."
    )

# --- هندلر پیام ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"):
        await update.message.reply_text("لطفاً لینک معتبر بفرست 📎")
        return

    await update.message.reply_text("⏳ در حال پردازش لینک...")

    aed_price = await get_aed_price()
    if not aed_price:
        await update.message.reply_text("❌ خطا در دریافت نرخ لحظه‌ای درهم.")
        return

    product_price_aed, weight_kg = await get_amazon_info(url)
    if not product_price_aed:
        await update.message.reply_text("❌ نتونستم قیمت محصول رو پیدا کنم.")
        return

    total_irr, extra_charge_irr = calculate_total(product_price_aed, aed_price, weight_kg)

    msg = f"💰 نرخ لحظه‌ای درهم: {aed_price:,.0f} تومان\n"
    msg += f"📦 قیمت محصول: {product_price_aed} AED\n"
    if weight_kg:
        msg += f"⚖️ وزن محصول: {weight_kg} kg\n"
    if extra_charge_irr > 0:
        msg += f"📦 هزینه اضافه بار: {extra_charge_irr:,.0f} تومان\n"
    msg += f"💵 قیمت نهایی: {total_irr:,.0f} تومان"

    await update.message.reply_text(msg)

# --- راه‌اندازی ربات ---
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

if __name__ == "__main__":
    app.run_polling()
