# Телеграм-бот «Персональный тренер, нутрициолог и наставник»

## Быстрый старт (локально)
1. Создайте `.env` из шаблона:
   ```bash
   cp .env.template .env
   ```
2. Заполните `TELEGRAM_BOT_TOKEN` и ключи API.
3. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
4. Запустите бота (long polling):
   ```bash
   python -m bot.main
   ```

SQLite создастся автоматически в `db/app.db`.