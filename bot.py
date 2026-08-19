import os

from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


load_dotenv(".env")


def required(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


TELEGRAM_BOT_TOKEN = required("TELEGRAM_BOT_TOKEN")
DEEPSEEK_API_KEY = required("DEEPSEEK_API_KEY")
try:
    ALLOWED_TELEGRAM_USER_ID = int(required("ALLOWED_TELEGRAM_USER_ID"))
except ValueError as exc:
    raise RuntimeError("ALLOWED_TELEGRAM_USER_ID must be numeric") from exc

DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
PROXY_URL = os.getenv("PROXY_URL", "").strip()

os.environ.pop("ALL_PROXY", None)
os.environ.pop("all_proxy", None)
if PROXY_URL:
    os.environ["HTTP_PROXY"] = PROXY_URL
    os.environ["HTTPS_PROXY"] = PROXY_URL

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    max_retries=0,
    timeout=60.0,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ALLOWED_TELEGRAM_USER_ID:
        return
    await update.message.reply_text("Telegram DeepSeek Bot is running.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ALLOWED_TELEGRAM_USER_ID:
        return

    history = context.user_data.setdefault("history", [])
    messages = history + [{"role": "user", "content": update.message.text}]

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
        )
        reply = response.choices[0].message.content or ""
    except Exception as exc:
        print(f"DeepSeek request failed: {type(exc).__name__}")
        await update.message.reply_text("Sorry, the AI request failed.")
        return

    history.extend([
        {"role": "user", "content": update.message.text},
        {"role": "assistant", "content": reply},
    ])
    history[:] = history[-20:]
    await update.message.reply_text(reply or "Sorry, the AI returned an empty response.")


def main():
    builder = Application.builder().token(TELEGRAM_BOT_TOKEN)
    if PROXY_URL:
        builder = builder.proxy(PROXY_URL).get_updates_proxy(PROXY_URL)

    application = builder.build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()


if __name__ == "__main__":
    main()
