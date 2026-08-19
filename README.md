# telegram-deepseek-bot

私人 Telegram AI Bot 项目。目标是使用 Telegram long polling 接收消息，通过 DeepSeek API 生成回复。

## 当前状态

项目初始化和最小 Telegram ↔ DeepSeek chat flow 已验证。当前使用 long polling，仅支持单用户文字消息；尚无 conversation memory，尚未配置 systemd。

## 技术栈

- Python 3.12
- `python-telegram-bot`
- OpenAI Python SDK（用于后续连接 DeepSeek 兼容 API）
- `python-dotenv`

## 本地/服务器运行

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python bot.py
```

当前入口不会读取 `.env`，也不会访问任何外部 API。后续常驻运行时再配置 systemd service。

## 环境变量

`.env.example` 中列出当前计划使用的变量：

- `TELEGRAM_BOT_TOKEN`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL`
- `ALLOWED_TELEGRAM_USER_ID`
- `DEEPSEEK_BASE_URL`

真实 `.env` 不应提交到 Git。

## 尚未实现

- Telegram Bot API long polling
- DeepSeek API 调用和 Telegram 回复
- 单用户访问控制
- SQLite 聊天记录与长期记忆
- systemd 常驻服务
