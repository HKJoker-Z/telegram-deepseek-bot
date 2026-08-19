import os
import sqlite3

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
DB_PATH = "chat.db"

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


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL
            )
            """
        )


def load_history(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT role, content
            FROM messages
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 20
            """,
            (user_id,),
        ).fetchall()
    return [{"role": role, "content": content} for role, content in reversed(rows)]


def save_exchange(user_id, user_text, assistant_text):
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
            [
                (user_id, "user", user_text),
                (user_id, "assistant", assistant_text),
            ],
        )
        conn.execute(
            """
            DELETE FROM messages
            WHERE user_id = ?
              AND id NOT IN (
                  SELECT id
                  FROM messages
                  WHERE user_id = ?
                  ORDER BY id DESC
                  LIMIT 20
              )
            """,
            (user_id, user_id),
        )


def clear_history(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))


def load_memories(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            """
            SELECT id, content
            FROM memories
            WHERE user_id = ?
            ORDER BY id
            """,
            (user_id,),
        ).fetchall()


def add_memory(user_id, content):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO memories (user_id, content) VALUES (?, ?)",
            (user_id, content),
        )


def delete_memory(user_id, memory_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "DELETE FROM memories WHERE id = ? AND user_id = ?",
            (memory_id, user_id),
        )
        return cursor.rowcount


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ALLOWED_TELEGRAM_USER_ID:
        return
    await update.message.reply_text("Telegram DeepSeek Bot is running.")


async def new_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ALLOWED_TELEGRAM_USER_ID:
        return
    clear_history(update.effective_user.id)
    await update.message.reply_text("New conversation started.")


async def remember(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ALLOWED_TELEGRAM_USER_ID:
        return

    content = " ".join(context.args).strip()
    if not content:
        await update.message.reply_text("Usage: /remember <text>")
        return

    add_memory(update.effective_user.id, content)
    await update.message.reply_text("Remembered.")


async def memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ALLOWED_TELEGRAM_USER_ID:
        return

    memories = load_memories(update.effective_user.id)
    if not memories:
        await update.message.reply_text("No saved memories.")
        return

    text = "\n".join(f"{memory_id}. {content}" for memory_id, content in memories)
    if len(text) > 4000:
        text = text[:3997] + "..."
    await update.message.reply_text(text)


async def forget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ALLOWED_TELEGRAM_USER_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /forget <id>")
        return

    try:
        memory_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Usage: /forget <id>")
        return

    if delete_memory(update.effective_user.id, memory_id):
        await update.message.reply_text("Memory deleted.")
    else:
        await update.message.reply_text("Memory not found.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ALLOWED_TELEGRAM_USER_ID:
        return

    user_id = update.effective_user.id
    user_text = update.message.text
    history = load_history(user_id)
    memories = load_memories(user_id)
    messages = []
    if memories:
        memory_text = "\n".join(f"- {content}" for _, content in memories)
        messages.append(
            {
                "role": "system",
                "content": (
                    "The following are long-term memories explicitly saved by the user. "
                    "Use them when relevant, do not mention them unnecessarily, and "
                    "treat the current user message as higher priority if it conflicts.\n\n"
                    + memory_text
                ),
            }
        )
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})

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

    save_exchange(user_id, user_text, reply)
    await update.message.reply_text(reply or "Sorry, the AI returned an empty response.")


def main():
    init_db()
    builder = Application.builder().token(TELEGRAM_BOT_TOKEN)
    if PROXY_URL:
        builder = builder.proxy(PROXY_URL).get_updates_proxy(PROXY_URL)

    application = builder.build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_conversation))
    application.add_handler(CommandHandler("remember", remember))
    application.add_handler(CommandHandler("memory", memory))
    application.add_handler(CommandHandler("forget", forget))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()


if __name__ == "__main__":
    main()
