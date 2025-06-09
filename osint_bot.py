import logging
import requests
from bs4 import BeautifulSoup
import phonenumbers
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from urllib.parse import quote_plus
import aiohttp
import datetime
import json
from pathlib import Path

# Константы
LOG_FILE = "bot_logs.txt"
BLACKLIST_FILE = "blacklist.json"
ADMIN_PASSWORD = "5&93?7!9_GujIAD"
TOKEN = "7735515311:AAGfbnBaOla-fClzuXLa9BVK9MuMG5eCFBQ"

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HIBP_API_URL = "https://haveibeenpwned.com/api/v3/breachedaccount/"
HIBP_API_KEY = ""  # Нет ключа

HEADERS = {"User-Agent": "OSINT-Bot"}
if HIBP_API_KEY:
    HEADERS["hibp-api-key"] = HIBP_API_KEY

def load_blacklist():
    if Path(BLACKLIST_FILE).exists():
        with open(BLACKLIST_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_blacklist(data):
    with open(BLACKLIST_FILE, "w") as f:
        json.dump(list(data), f)

blacklist = load_blacklist()

def log_event(user, command, args):
    time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{time}] {user} → {command} {args}\n")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Используй /menu для просмотра доступных команд.")

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📋 Меню бота:\n\n"
        "/check_email <email> — Проверка email через HIBP\n"
        "/check_phone <номер> — Проверка телефона и имя\n"
        "/check_twin <email|номер> — Поиск возможных твинков\n"
        "/admin_panel <пароль> — Панель логов администратора\n"
    )
    await update.message.reply_text(msg)

async def check_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ Пример: /check_email test@example.com")
        return
    email = context.args[0].lower()
    if email in blacklist:
        await update.message.reply_text("❌ Этот email запрещён для поиска.")
        return
    log_event(update.effective_user.username, "/check_email", email)
    msg = f"🔍 Проверка email: {email}\n\n"
    url = HIBP_API_URL + email
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=HEADERS) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    leaks = [breach["Name"] for breach in data]
                    msg += f"⚠️ Найден в утечках:\n" + "\n".join(leaks)
                elif resp.status == 404:
                    msg += "✅ Утечек по email не найдено."
                elif resp.status == 429:
                    msg += "⏳ Превышен лимит запросов, попробуй позже."
                else:
                    msg += f"❌ Ошибка HIBP: {resp.status}"
        except Exception as e:
            msg += f"❌ Ошибка запроса: {e}"
    msg += f"\n\n🔗 Google: https://www.google.com/search?q={quote_plus(email)}"
    await update.message.reply_text(msg)

async def check_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ Пример: /check_phone +79991234567")
        return
    number = context.args[0]
    if number in blacklist:
        await update.message.reply_text("❌ Этот номер запрещён для поиска.")
        return
    log_event(update.effective_user.username, "/check_phone", number)
    try:
        parsed = phonenumbers.parse(number, None)
        valid = phonenumbers.is_valid_number(parsed)
        region = phonenumbers.region_code_for_number(parsed)
        carrier_name = phonenumbers.carrier.name_for_number(parsed, "ru")

        msg = (
            f"📞 Номер: {number}\n"
            f"🌍 Страна: {region}\n"
            f"📡 Оператор: {carrier_name or 'Неизвестен'}\n"
            f"✅ Валидность: {'Да' if valid else 'Нет'}\n\n"
        )

        sites = [
            {
                "name": "FreePhoneTracer","url": f"https://www.freephonetracer.com/phone/{quote_plus(number)}"
            },
            {
                "name": "PhoneNumberInfo",
                "url": f"https://phonenumberinfo.net/phone/{quote_plus(number)}"
            }
        ]

        for site in sites:
            try:
                r = requests.get(site["url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    owner = soup.find(id="owner-name")
                    msg += f"👤 {site['name']}: {owner.text.strip() if owner else 'Нет данных'}\n"
                elif r.status_code in [403, 401]:
                    msg += f"⚠️ {site['name']} → Авторизация/Captcha\n🔗 {site['url']}\n"
                else:
                    msg += f"❌ {site['name']} → Ошибка {r.status_code}\n🔗 {site['url']}\n"
            except Exception as e:
                msg += f"❌ Ошибка {site['name']}: {e}\n🔗 {site['url']}\n"

        msg += (
            f"\n🔗 Google: https://www.google.com/search?q={quote_plus(number)}\n"
            f"🔗 Telegram: https://t.me/s/{quote_plus(number)}"
        )
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def check_twin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ Пример: /check_twin email/номер")
        return
    idn = context.args[0]
    if idn in blacklist:
        await update.message.reply_text("❌ Этот идентификатор запрещён для поиска.")
        return
    log_event(update.effective_user.username, "/check_twin", idn)
    links = [
        f"https://vk.com/search?c%5Bq%5D={quote_plus(idn)}&c%5Bsection%5D=people",
        f"https://t.me/s/{quote_plus(idn)}",
        f"https://www.google.com/search?q={quote_plus(idn)}",
        f"https://instagram.com/{quote_plus(idn)}",
        f"https://facebook.com/search/top?q={quote_plus(idn)}",
        f"https://twitter.com/search?q={quote_plus(idn)}",
        f"https://github.com/search?q={quote_plus(idn)}"
    ]
    msg = f"🧭 Поиск твинков по: {idn}\n\n"
    for link in links:
        msg += f"🔗 {link}\n"
    await update.message.reply_text(msg)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global blacklist
    if not context.args or context.args[0] != ADMIN_PASSWORD:
        await update.message.reply_text("❌ Неверный пароль.")
        return

    # Бан идентификатора
    if len(context.args) >= 3 and context.args[1] == "ban":
        target = context.args[2]
        blacklist.add(target)
        save_blacklist(blacklist)
        await update.message.reply_text(f"🚫 {target} добавлен в стоп-лист.")
        return

    try:
        with open(LOG_FILE, "r") as f:
            logs = f.read()
        await update.message.reply_text(f"📋 Последние логи:\n\n{logs[-4000:]}")
    except FileNotFoundError:
        await update.message.reply_text("❌ Лог-файл не найден.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("check_email", check_email))
    app.add_handler(CommandHandler("check_phone", check_phone))
    app.add_handler(CommandHandler("check_twin", check_twin))
    app.add_handler(CommandHandler("admin_panel", admin_panel))

    print("🤖 Бот запущен.")
    app.run_polling()
