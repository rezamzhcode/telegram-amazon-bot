import os
import re
import httpx
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SHIPPING_FLAT_AED = float(os.getenv("SHIPPING_FLAT_AED", 15))
CUSTOMS_PERCENT = float(os.getenv("CUSTOMS_PERCENT", 10))
SERVICE_FEE_PERCENT = float(os.getenv("SERVICE_FEE_PERCENT", 10))
EXTRA_PER_50KG_IRR = int(os.getenv("EXTRA_PER_50KG_IRR", 500_000))
MAX_WEIGHT_KG = 50
AED_TO_IRR_MANUAL = int(os.getenv("AED_TO_IRR_MANUAL", 150000))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! لطفاً لینک محصول آمازون دبی خود را ارسال کنید.")

def fix_amazon_link(url: str) -> str:
    """لینک EU را به AE تبدیل می‌کند."""
    url = url.replace(".eu", ".ae")
    return url

async def get_aed_to_irr() -> int:
    """نرخ لحظه‌ای درهم از سایت TGJU."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://www.tgju.org/profile/price_aed")
            soup = BeautifulSoup(resp.text, "lxml")
            td = soup.find("td", class_="text-left")
            if td:
                return int(td.text.replace(",", "").strip())
    except:
        pass
    return AED_TO_IRR_MANUAL

async def parse_amazon_product(url: str) -> dict:
    """قیمت و وزن محصول را از صفحه آمازون استخراج می‌کند."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "lxml")
        # قیمت
        price_tag = soup.find("span", class_="a-price-whole")
        price = float(price_tag.text.replace(",", "")) if price_tag else None
        # وزن
        weight = 0
        text_elements = soup.find_all(text=re.compile(r"(Weight|وزن)"))
        for t in text_elements:
            match = re.search(r"([\d,.]+)\s*kg", t, re.IGNORECASE)
            if match:
                weight = float(match.group(1).replace(",", "."))
                break
        return {"price_aed": price, "weight_kg": weight}

def calculate_final(price_aed, weight_kg, aed_to_irr):
    shipping_irr = SHIPPING_FLAT_AED * aed_to_irr
    customs_irr = price_aed * aed_to_irr * CUSTOMS_PERCENT / 100
    service_irr = price_aed * aed_to_irr * SERVICE_FEE_PERCENT / 100
    extra_weight_irr = 0
    if weight_kg > MAX_WEIGHT_KG:
        extra_units = int((weight_kg - MAX_WEIGHT_KG) / MAX_WEIGHT_KG) + 1
        extra_weight_irr = extra_units * EXTRA_PER_50KG_IRR
    total = price_aed * aed_to_irr + shipping_irr + customs_irr + service_irr + extra_weight_irr
    return {
        "total_toman": total // 10,
        "shipping_toman": shipping_irr // 10,
        "customs_toman": customs_irr // 10,
        "service_toman": service_irr // 10,
        "extra_weight_toman": extra_weight_irr // 10
    }

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if "amazon" not in url:
        await update.message.reply_text("⚠️ لطفاً یک لینک معتبر از آمازون بفرست.")
        return

    url = fix_amazon_link(url)
    await update.message.reply_text("⏳ در حال بررسی محصول و نرخ لحظه‌ای درهم...")

    aed_to_irr = await get_aed_to_irr()
    product = await parse_amazon_product(url)
    if not product["price_aed"]:
        await update.message.reply_text("❌ قیمت محصول پیدا نشد. مطمئن شوید لینک درست است.")
        return

    result = calculate_final(product["price_aed"], product["weight_kg"], aed_to_irr)

    response = f"""💱 نرخ لحظه‌ای درهم: {aed_to_irr // 10:,} تومان
🛒 قیمت کالا: {product['price_aed']} AED
📦 هزینه ارسال: {SHIPPING_FLAT_AED} AED
⚖️ وزن محصول: {product['weight_kg']} کیلوگرم
🛃 گمرک: {CUSTOMS_PERCENT}%
💰 کارمزد: {SERVICE_FEE_PERCENT}%
➕ اضافه‌بار: {result['extra_weight_toman']:,} تومان
🏁 قیمت نهایی تقریبی: {result['total_toman']:,} تومان
"""
    await update.message.reply_text(response)

if __name__ == "__main__":
    # استفاده از polling امن برای Railway و جلوگیری از Conflict
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot is running...")
    app.run_polling()
