import os
import re
import json
import asyncio
import requests
from datetime import date, datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

DATA_DIR = "data"
NEWS_FILE = f"{DATA_DIR}/flash_news.json"
USER_FILE = f"{DATA_DIR}/users.json"
BASE_URL = "https://loyolacollege.edu/"

def safe_escape(text: str) -> str:
    escape_chars = r'[_*[\]()~`>#+\-=|{}.!]'
    return re.sub(escape_chars, lambda m: '\\' + m.group(0), text.strip())

def process_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("../../"):
        return BASE_URL + url[3:]
    if url.startswith("../"):
        return BASE_URL + url[2:]
    return url

def load_json(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)

def save_json(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

def today_iso() -> str:
    return date.today().isoformat()

def today_display() -> str:
    return date.today().strftime("%d-%m-%Y")

async def send_today_notices(bot: Bot, chat_id: int):
    today = today_iso()
    display_date = today_display()

    if not os.path.isfile(NEWS_FILE):
        return

    with open(NEWS_FILE, "r") as f:
        all_news = json.load(f)

    today_news = [item for item in all_news if item["date"] == today]

    for item in today_news:
        safe_notice = safe_escape(item["notice"])
        message = f"📢 *Notice:*\n{safe_notice}\n\n📅 *Date:*\n{safe_escape(display_date)}"
        if item.get("url"):
            safe_url = safe_escape(item["url"])
            message += f"\n\n🔗 *URL:*\n{safe_url}"

        try:
            await bot.send_message(chat_id=chat_id, text=message, parse_mode="MarkdownV2")
            print(f"📬 Sent today's notice to {chat_id}")
        except Exception as e:
            print(f"❌ Error sending to {chat_id}: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_info = update.effective_user
    chat_id = update.effective_chat.id
    today = today_display()

    data = load_json(USER_FILE)
    users = data.get("users", [])

    if any(u["chat_id"] == chat_id for u in users):
        await update.message.reply_text("📢 You’re already subscribed!")
        print(f"🟡 User {chat_id} already subscribed.")
        return

    full_name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()

    new_user = {
        "serial": len(users) + 1,
        "chat_id": chat_id,
        "subscribed_at": today,
        "username": user_info.username or "N/A",
        "name": full_name or "N/A"
    }

    users.append(new_user)
    save_json(USER_FILE, {"users": users})

    await update.message.reply_text("✅ You’re now subscribed to Loyola Flash News!\nSending today’s notices now…")
    print(f"🟢 New user subscribed: {chat_id} ({new_user['username']})")

    await send_today_notices(context.bot, chat_id)

async def broadcast_message(bot: Bot, message: str, today_str: str):
    data = load_json(USER_FILE)
    users = data.get("users", [])
    for user in users:
        joined = user.get("subscribed_at", today_str)
        try:
            joined_dt = datetime.strptime(joined, "%d-%m-%Y").date()
            today_dt = datetime.strptime(today_display(), "%d-%m-%Y").date()
            if joined_dt <= today_dt:
                await bot.send_message(chat_id=int(user["chat_id"]), text=message, parse_mode="MarkdownV2")
                print(f"✅ Sent to {user['chat_id']}")
        except Exception as e:
            print(f"❌ Error sending to {user['chat_id']}: {e}")

async def fetch_and_send_news(bot: Bot):
    today = today_iso()
    display_date = today_display()
    os.makedirs(DATA_DIR, exist_ok=True)

    existing_data = []
    if os.path.isfile(NEWS_FILE):
        with open(NEWS_FILE, "r") as f:
            existing_data = json.load(f)

    try:
        response = requests.get(BASE_URL, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"🚫 Request failed: {e}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    wrapper = soup.find("div", class_="partner-wrapper hero-slider owl-carousel owl-theme")

    if not wrapper:
        print("😢 No matching content found.")
        return

    list_items = wrapper.find_all("li")
    new_items = []

    for index, item in enumerate(list_items, start=1):
        notice = item.get_text(strip=True)
        link_tag = item.find("a")
        raw_url = link_tag["href"] if link_tag and link_tag.has_attr("href") else None
        processed_url = process_url(raw_url)

        is_duplicate = any(
            d["notice"] == notice and d["date"] == today
            for d in existing_data
        )

        if is_duplicate:
            print(f"⚠️ Duplicate skipped: {notice}")
            continue

        safe_notice = safe_escape(notice)
        message = f"📢 *Notice:*\n{safe_notice}\n\n📅 *Date:*\n{safe_escape(display_date)}"
        if processed_url:
            safe_url = safe_escape(processed_url)
            message += f"\n\n🔗 *URL:*\n{safe_url}"

        await broadcast_message(bot, message, today)

        item_data = {
            "serial_number": index,
            "notice": notice,
            "date": today,
            "url": processed_url
        }
        new_items.append(item_data)
        existing_data.append(item_data)

    with open(NEWS_FILE, "w") as f:
        json.dump(existing_data, f, indent=4)

    print(f"✅ Scraping complete. {len(new_items)} new items sent.")

async def periodic_task(application: Application):
    while True:
        print("🔁 Checking for new news...")
        await fetch_and_send_news(application.bot)
        await asyncio.sleep(3600)  # Every hour

async def post_init(application: Application):
    asyncio.create_task(periodic_task(application))

def main():
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    print("🚀 Bot is running. Ctrl+C to stop.")
    application.run_polling()

if __name__ == "__main__":
    main()