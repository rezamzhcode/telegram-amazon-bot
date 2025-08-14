# bot.py
import os
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# ==========================
# تنظیمات اولیه
# ==========================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# نرخ تبدیل دستی (درهم به تومان)
AED_TO_IRR = 150000  # مثلا 1 درهم = 150,000 تومان

# هزینه‌ها
SHIPPING_AED = 15       # هزینه ارسال به درهم
CUSTOMS_PERCENT = 10    # گمرک درصد
SERVICE_PERCENT = 10    # کارمزد درصد
EXTRA_PER_50KG_IRR = 500000  # هر 50 کیلو اضافه 500 هزار تومان

# ==========================
# تابع دریافت قیمت و وزن محصول
# ==========================
def fetch_amazon(url):
    # اطمینان از اینکه لینک AED هست
    if "eu" in url:
        url = url.replace(".eu", ".ae")

    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        return None

    soup = BeautifulSoup(res.text, "lxml")

    # قیمت محصول
    price_tag = soup.select_one("span.a-price-whole")
    if not price_tag:
        return None
    price_aed = float(price_tag.text.replace(",", "").strip())

    # وزن محصول
    weight_tag = soup.find(string=lambda t: "kg" in t.lower())
    weight_kg = 0
    if weight_tag:
        import re
        m = re.search(r"(\d+\.?\d*)\s*kg", weight_tag.lower())
        if m:
            weight_kg = float(m.group(1))

    return price_aed, weight_kg

# ==========================
# محاسبه قیمت نهایی
# ==========================
def calculate_final(price_aed, weight_kg):
    shipping_toman = SHIPPING_AED * AED_TO_IRR
    base_price_toman = price_aed * AED_TO_IRR
    customs = (base_price_toman + shipping_toman) * (CUSTOMS_PERCENT / 100)
    service = (base_price_toman + shipping_toman) * (SERVICE_PERCENT / 100)
    extra_weight = max(0, weight_kg - 50)
    extra_cost = ((extra_weight // 50) + (1 if extra_weight % 50 > 0 else 0)) * EXTRA_PER_50KG_IRR

    total = base_price_toman + shipping_toman + customs + service + extra_cost
    return total, shipping_toman, customs, service, extra_cost

# ==========================
# هندلر start
# ==========================
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "سلام! لطفاً لینک محصول آمازون دبی (AED) یا EU ارسال کن. ربات لینک EU را به AE تبدیل می‌کند."
    )

# ==========================
# هندلر پیام‌ها
# ==========================
def handle_message(update: Update, context: CallbackContext):
    url = update.message.text.strip()
    result = fetch_amazon(url)
    if not result:
        update.message.reply_text("⚠️ لطفاً یک لینک معتبر از آمازون بفرست.")
        return

    price_aed, weight_kg = result
    total, shipping_toman, customs, service, extra_cost = calculate_final(price_aed, weight_kg)

    msg = f"""
💱 نرخ درهم: {AED_TO_IRR} تومان
🛒 قیمت کالا: {price_aed} AED
📦 هزینه ارسال: {shipping_toman:,} تومان
🛃 گمرک: {customs:,} تومان
💵 کارمزد: {service:,} تومان
⚖️ وزن محصول: {weight_kg} کیلوگرم
➕ هزینه اضافه وزن: {extra_cost:,} تومان
🏁 قیمت نهایی: {total:,} تومان
"""
    update.message.reply_text(msg)

# ==========================
# اجرای ربات
# ==========================
def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
