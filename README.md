# telegram-deepseek-bot

私人 Telegram AI Bot 项目。目标是使用 Telegram long polling 接收消息，通过 DeepSeek API 生成回复。

## 当前状态

项目初始化和最小 Telegram ↔ DeepSeek chat flow 已验证。当前使用 long polling，仅支持单用户文字消息，并通过 SQLite 持久化最近 10 轮对话；支持 `/start` 和 `/new`。Bot 已由 systemd 常驻管理，开机启动已启用，异常退出会自动重启。

## 技术栈

- Python 3.12
- `python-telegram-bot`
- OpenAI Python SDK（用于连接 DeepSeek 兼容 API）
- `python-dotenv`

## 本地/服务器运行

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python bot.py
```

当前入口会读取 `.env`、初始化项目根目录的 `chat.db` 并访问 Telegram/DeepSeek。`/new` 会清空当前用户的对话历史；systemd service 负责长期运行。

systemd 管理命令：

```bash
sudo systemctl status telegram-deepseek-bot
sudo systemctl restart telegram-deepseek-bot
journalctl -u telegram-deepseek-bot -f
```

## 环境变量

`.env.example` 中列出当前计划使用的变量：

- `TELEGRAM_BOT_TOKEN`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL`
- `ALLOWED_TELEGRAM_USER_ID`
- `DEEPSEEK_BASE_URL`
- `PROXY_URL`

真实 `.env` 不应提交到 Git。

## 当前未使用

- 长期记忆
