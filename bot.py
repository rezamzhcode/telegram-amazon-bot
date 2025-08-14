import os
import re
import httpx
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AED_TO_IRR = int(os.getenv("AED_TO_IRR_MANUAL", 150000))
SHIPPING_FLAT = float(os.getenv("SHIPPING_FLAT_AED", 15))
CUSTOMS_PERCENT = float(os.getenv("CUSTOMS_PERCENT", 10))
SERVICE_FEE_PERCENT = float(os.getenv("SERVICE_FEE_PERCENT", 10))
EXTRA_FIXED = float(os.getenv("EXTRA_FIXED_IRR", 0))
AS_TOMAN = os.getenv("AS_TOMAN", "true").lower() == "true"

def normalize_amazon_link(link):
    if "amazon.eu" in link:
        link = link.replace("amazon.eu", "amazon.ae")
    return link

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! لینک محصول آمازون دبی رو بفرست تا قیمت به تومان برات محاسبه کنم.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_link = update.message.text.strip()
    if not ("amazon.ae" in user_link or "amazon.eu" in user_link):
        await update.message.reply_text("⚠️ لطفاً یک لینک معتبر از آمازون بفرست.")
        return

    link = normalize_amazon_link(user_link)
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(link, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "lxml")

        # قیمت محصول
        price_tag = soup.select_one("#priceblock_ourprice, #priceblock_dealprice")
        if price_tag is None:
            price_tag = soup.find("span", {"class": "a-offscreen"})
        if price_tag is None:
            await update.message.reply_text("😅، قیمت محصول پیدا نشد! مطمئن شو لینک آمازون دبی است و دوباره امتحان کن.")
            return
        price_aed = float(re.sub(r"[^\d.]", "", price_tag.text))

        # وزن محصول
        weight_text = ""
        weight_tag = soup.find("td", string=re.compile(r"Shipping Weight|وزن"))
        weight_kg = 0
        if weight_tag:
            sibling = weight_tag.find_next_sibling("td")
            if sibling:
                weight_text = sibling.text.strip()
                match = re.search(r"([\d,.]+)\s*(kg|g|pounds|lbs)", weight_text, re.IGNORECASE)
                if match:
                    val, unit = match.groups()
                    val = float(val.replace(",", ""))
                    if unit.lower() in ["g"]:
                        weight_kg = val / 1000
                    elif unit.lower() in ["pounds", "lbs"]:
                        weight_kg = val * 0.453592
                    else:
                        weight_kg = val

        # اضافه بار
        extra_weight = max(0, weight_kg - 50)
        extra_fee = extra_weight * 500  # هر 50 کیلو اضافه 500 تومان
        if AS_TOMAN:
            conversion = AED_TO_IRR / 10
        else:
            conversion = AED_TO_IRR

        shipping_cost = SHIPPING_FLAT * conversion
        product_cost = price_aed * conversion
        customs = product_cost * (CUSTOMS_PERCENT/100)
        service_fee = product_cost * (SERVICE_FEE_PERCENT/100)

        total = product_cost + shipping_cost + customs + service_fee + extra_fee + EXTRA_FIXED

        msg = f"""💱 نرخ درهم (تومان): {int(AED_TO_IRR/10)}
🛒 قیمت کالا: {price_aed} AED
📦 هزینه ارسال: {SHIPPING_FLAT} AED ({int(shipping_cost)} تومان)
⚖️ وزن محصول: {weight_kg:.2f} کیلوگرم
➕ اضافه بار: {extra_fee:.0f} تومان
🛃 گمرک: {CUSTOMS_PERCENT}% ({int(customs)} تومان)
💵 درصد کارمزد: {SERVICE_FEE_PERCENT}% ({int(service_fee)} تومان)
🏁 قیمت نهایی: {int(total)} تومان"""

        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(f"خطا در پردازش لینک: {e}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot is running...")
    app.run_polling()
