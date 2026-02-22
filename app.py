import asyncio
import logging
import os
import threading
from flask import Flask, request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler

from config import BOT_TOKEN, WEBHOOK_URL
from database import init_db
from handlers.admin import (
    admin_add_video_handler,
    admin_command,
    admin_delete_user_callback_handler,
    admin_delete_video_callback_handler,
    admin_manage_videos_handler,
    admin_view_users_handler,
)
from handlers.user import registration_handler, video_selection_handler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Railway provides PORT via env var
PORT = int(os.getenv("PORT", "8080"))

application = Flask(__name__)

telegram_app: Application | None = None
event_loop: asyncio.AbstractEventLoop | None = None
loop_thread: threading.Thread | None = None


def setup_application() -> Application:
    logger.info("Setting up Telegram application...")

    # Initialize database (creates tables)
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    app.add_handler(admin_delete_user_callback_handler, group=0)
    app.add_handler(admin_delete_video_callback_handler, group=0)
    app.add_handler(admin_add_video_handler, group=0)
    app.add_handler(admin_view_users_handler, group=0)
    app.add_handler(admin_manage_videos_handler, group=0)
    app.add_handler(CommandHandler("admin", admin_command), group=0)

    app.add_handler(registration_handler, group=1)
    app.add_handler(video_selection_handler, group=2)

    logger.info("Telegram application setup complete")
    return app


@application.route("/webhook", methods=["POST"])
def webhook():
    global telegram_app, event_loop

    if telegram_app is None or event_loop is None:
        return Response(status=503)

    try:
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, telegram_app.bot)

        # Schedule update processing without blocking HTTP response
        asyncio.run_coroutine_threadsafe(telegram_app.process_update(update), event_loop)

        return Response(status=200)

    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return Response(status=500)


@application.route("/")
def index():
    return "Telegram Bot is running!"


@application.route("/health")
def health():
    return {"status": "ok", "bot": "running"}


async def setup_webhook():
    """
    Hard reset webhook to avoid Telegram caching / stale webhook issues.
    """
    global telegram_app
    if telegram_app is None:
        raise RuntimeError("telegram_app is not initialized")

    if not WEBHOOK_URL or not WEBHOOK_URL.startswith("https://"):
        raise RuntimeError("WEBHOOK_URL must be set and start with https://")

    logger.info(f"Resetting webhook to: {WEBHOOK_URL}")

    # Drop pending updates and force set correct webhook URL
    await telegram_app.bot.delete_webhook(drop_pending_updates=True)
    await telegram_app.bot.set_webhook(url=WEBHOOK_URL)

    info = await telegram_app.bot.get_webhook_info()
    logger.info(f"Webhook is now: {info.url}")


async def remove_webhook():
    global telegram_app
    if telegram_app is None:
        return
    try:
        logger.info("Removing webhook...")
        await telegram_app.bot.delete_webhook()
        logger.info("Webhook removed")
    except Exception as e:
        logger.error(f"Failed to remove webhook: {e}")


def _start_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


def main():
    global telegram_app, event_loop, loop_thread

    logger.info("Starting Telegram bot in webhook mode...")

    telegram_app = setup_application()

    event_loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=_start_event_loop, args=(event_loop,), daemon=True)
    loop_thread.start()

    # Start the telegram app on the background loop
    asyncio.run_coroutine_threadsafe(telegram_app.initialize(), event_loop).result()
    asyncio.run_coroutine_threadsafe(telegram_app.start(), event_loop).result()
    asyncio.run_coroutine_threadsafe(setup_webhook(), event_loop).result()

    logger.info(f"Starting Flask server on port {PORT}...")
    try:
        application.run(host="0.0.0.0", port=PORT, debug=False)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        if event_loop is not None and telegram_app is not None:
            asyncio.run_coroutine_threadsafe(remove_webhook(), event_loop).result()
            asyncio.run_coroutine_threadsafe(telegram_app.stop(), event_loop).result()
            asyncio.run_coroutine_threadsafe(telegram_app.shutdown(), event_loop).result()
            event_loop.call_soon_threadsafe(event_loop.stop)
        if loop_thread is not None:
            loop_thread.join(timeout=5)


if __name__ == "__main__":
    main()