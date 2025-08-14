import os
import re
import httpx
from bs4 import BeautifulSoup
from telegram import Update, ForceReply
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SHIPPING_FLAT_AED = float(os.getenv("SHIPPING_FLAT_AED", 15))
CUSTOMS_PERCENT = float(os.getenv("CUSTOMS_PERCENT", 10))
SERVICE_FEE_PERCENT = float(os.getenv("SERVICE_FEE_PERCENT", 10))
EXTRA_FIXED_IRR = float(os.getenv("EXTRA_FIXED_IRR", 0))
AED_TO_IRR_MANUAL = float(os.getenv("AED_TO_IRR_MANUAL", 15000))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "سلام! لینک محصول آمازون دبی (AE یا EU) را ارسال کنید تا قیمت نهایی را حساب کنم.",
        reply_markup=ForceReply(selective=True),
    )

def convert_eu_to_ae(url: str) -> str:
    return re.sub(r'\.eu/', '.ae/', url)

async def get_aed_rate() -> float:
    url = "https://www.tgju.org/profile/price_aed"
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
        soup = BeautifulSoup(r.text, "lxml")
        td = soup.find("td", class_="text-left")
        if td:
            text = td.get_text().replace(",", "")
            try:
                return float(text)
            except:
                return AED_TO_IRR_MANUAL
        return AED_TO_IRR_MANUAL

async def get_product_info(url: str):
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "lxml")
        price_tag = soup.find("span", {"id": re.compile(r"priceblock_.*")})
        if price_tag:
            price_text = re.sub(r"[^\d.]", "", price_tag.get_text())
            price_aed = float(price_text)
        else:
            price_aed = None
        weight_text = soup.find(string=re.compile(r"(\d+(\.\d+)?)\s?kg"))
        weight_kg = float(re.search(r"(\d+(\.\d+)?)", weight_text).group()) if weight_text else 0
        return price_aed, weight_kg

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    url = update.message.text.strip()
    if "amazon" not in url:
        await update.message.reply_text("⚠️ لطفاً یک لینک معتبر از آمازون بفرست.")
        return

    url = convert_eu_to_ae(url)

    price_aed, weight_kg = await get_product_info(url)
    if price_aed is None:
        await update.message.reply_text("💥 اوپس، قیمت محصول پیدا نشد!")
        return

    rate = await get_aed_rate()
    shipping_irr = SHIPPING_FLAT_AED * rate
    customs_irr = price_aed * rate * CUSTOMS_PERCENT / 100
    service_fee_irr = price_aed * rate * SERVICE_FEE_PERCENT / 100
    extra_weight_irr = 0
    if weight_kg > 50:
        extra_units = (weight_kg - 50) // 50 + 1
        extra_weight_irr = extra_units * 500_000

    total_irr = price_aed * rate + shipping_irr + customs_irr + service_fee_irr + extra_weight_irr + EXTRA_FIXED_IRR

    await update.message.reply_text(
        f"💱 نرخ لحظه‌ای درهم: {int(rate):,} تومان\n"
        f"🛒 قیمت محصول: {price_aed} AED\n"
        f"📦 هزینه ارسال: {SHIPPING_FLAT_AED} AED ({int(shipping_irr):,} تومان)\n"
        f"⚖️ وزن کالا: {weight_kg} کیلو\n"
        f"🛃 گمرک ({CUSTOMS_PERCENT}%): {int(customs_irr):,} تومان\n"
        f"💵 کارمزد ({SERVICE_FEE_PERCENT}%): {int(service_fee_irr):,} تومان\n"
        f"📈 اضافه‌بار: {int(extra_weight_irr):,} تومان\n"
        f"🏁 قیمت نهایی: {int(total_irr):,} تومان"
    )

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
