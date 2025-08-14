import os
import re
import math
import httpx
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AED_TO_IRR_MANUAL = float(os.getenv("AED_TO_IRR_MANUAL", 150000))
SHIPPING_FLAT_AED = float(os.getenv("SHIPPING_FLAT_AED", 15))
CUSTOMS_PERCENT = float(os.getenv("CUSTOMS_PERCENT", 10))
SERVICE_FEE_PERCENT = float(os.getenv("SERVICE_FEE_PERCENT", 10))
EXTRA_FIXED_IRR = float(os.getenv("EXTRA_FIXED_IRR", 0))
AS_TOMAN = True  # تبدیل به تومان

def fix_amazon_link(link: str) -> str:
    # تبدیل لینک EU به AE
    if "amazon.eu" in link:
        link = link.replace("amazon.eu", "amazon.ae")
    return link

async def fetch_aed_to_irr():
    # نرخ دستی، برای ساده بودن
    return AED_TO_IRR_MANUAL

async def fetch_product_data(link):
    async with httpx.AsyncClient() as client:
        r = await client.get(link, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "lxml")

        # قیمت محصول
        price_tag = soup.find("span", {"id": re.compile(r"priceblock_.*")})
        if not price_tag:
            return None
        price_aed = float(re.sub(r"[^\d.]", "", price_tag.get_text()))

        # وزن کالا
        weight_tag = soup.find(string=re.compile(r"Weight|وزن", re.I))
        weight = 0
        if weight_tag:
            parent = weight_tag.find_parent()
            if parent:
                weight_match = re.search(r"([\d,.]+)\s*kg", parent.get_text(), re.I)
                if weight_match:
                    weight = float(weight_match.group(1).replace(",", ""))

        return {"price_aed": price_aed, "weight_kg": weight}

def calculate_final_price(price_aed, weight_kg, aed_to_irr):
    # محاسبه هزینه‌ها
    shipping_aed = SHIPPING_FLAT_AED
    customs_fee = (price_aed + shipping_aed) * (CUSTOMS_PERCENT / 100)
    service_fee = (price_aed + shipping_aed + customs_fee) * (SERVICE_FEE_PERCENT / 100)
    
    # اضافه بار
    extra_weight_fee = 0
    if weight_kg > 50:
        extra_units = math.ceil((weight_kg - 50) / 50)
        extra_weight_fee = extra_units * 500_000  # هر 50 کیلو اضافه 500 هزار تومان

    total_irr = (price_aed + shipping_aed + customs_fee + service_fee) * aed_to_irr + EXTRA_FIXED_IRR + extra_weight_fee
    if AS_TOMAN:
        total_irr = total_irr / 10  # تبدیل به تومان

    return total_irr, shipping_aed, customs_fee, service_fee, extra_weight_fee

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_link = update.message.text.strip()
    user_link = fix_amazon_link(user_link)

    if "amazon.ae" not in user_link:
        await update.message.reply_text("⚠️ لطفاً یک لینک معتبر از آمازون بفرست.")
        return

    await update.message.reply_text("⏳ در حال بررسی محصول...")

    data = await fetch_product_data(user_link)
    if not data:
        await update.message.reply_text("❌ اوپس 😅، قیمت محصول پیدا نشد! مطمئن شو لینک آمازون دبی است و دوباره امتحان کن.")
        return

    aed_to_irr = await fetch_aed_to_irr()
    total_price, shipping_aed, customs_fee, service_fee, extra_weight_fee = calculate_final_price(
        data["price_aed"], data["weight_kg"], aed_to_irr
    )

    msg = (
        f"💱 نرخ لحظه‌ای درهم: {int(aed_to_irr / 10 if AS_TOMAN else aed_to_irr)} تومان\n"
        f"🛒 قیمت محصول: {data['price_aed']} AED\n"
        f"📦 هزینه ارسال: {shipping_aed} AED\n"
        f"🛃 گمرک ({CUSTOMS_PERCENT}%): {int(customs_fee)} AED\n"
        f"💵 درصد کارمزد ({SERVICE_FEE_PERCENT}%): {int(service_fee)} AED\n"
    )
    if extra_weight_fee:
        msg += f"⚠️ هزینه اضافه بار: {int(extra_weight_fee)} تومان\n"
    msg += f"🏁 قیمت نهایی: {int(total_price)} تومان\n"
    if data["weight_kg"]:
        msg += f"⚖️ وزن کالا: {data['weight_kg']} کیلوگرم"

    await update.message.reply_text(msg)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot started...")
    app.run_polling()
