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
    addadmin_handler,
)

from handlers.user import registration_handler

# -----------------------
# Logging
# -----------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

PORT = int(os.getenv("PORT", "8080"))

# -----------------------
# Flask App
# -----------------------
application = Flask(__name__)

telegram_app: Application | None = None
event_loop: asyncio.AbstractEventLoop | None = None
loop_thread: threading.Thread | None = None


# -----------------------
# Error Logging
# -----------------------
async def on_error(update, context):
    logger.exception("Handler error:", exc_info=context.error)


# -----------------------
# Setup Telegram
# -----------------------
def setup_application() -> Application:
    logger.info("Setting up Telegram application...")

    # Ensure DB tables exist
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # -------- Admin Handlers --------
    app.add_handler(addadmin_handler, group=0)
    app.add_handler(CommandHandler("admin", admin_command), group=0)
    app.add_handler(admin_add_video_handler, group=0)
    app.add_handler(admin_view_users_handler, group=0)
    app.add_handler(admin_manage_videos_handler, group=0)
    app.add_handler(admin_delete_user_callback_handler, group=0)
    app.add_handler(admin_delete_video_callback_handler, group=0)

    # -------- User Conversation --------
    app.add_handler(registration_handler, group=2)

    # -------- Error handler --------
    app.add_error_handler(on_error)

    logger.info("Telegram application setup complete")
    return app


# -----------------------
# Webhook Route
# -----------------------
@application.route("/webhook", methods=["POST"])
def webhook():
    global telegram_app, event_loop

    if telegram_app is None or event_loop is None:
        return Response(status=503)

    try:
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, telegram_app.bot)

        future = asyncio.run_coroutine_threadsafe(
            telegram_app.process_update(update), event_loop
        )

        # Log internal exceptions
        def _log_future(f):
            try:
                f.result()
            except Exception as e:
                logger.exception(f"process_update crashed: {e}")

        future.add_done_callback(_log_future)

        return Response(status=200)

    except Exception as e:
        logger.error(f"Webhook parse error: {e}")
        return Response(status=500)


# -----------------------
# Health Routes
# -----------------------
@application.route("/")
def index():
    return "Telegram Bot is running!"


@application.route("/health")
def health():
    return {"status": "ok", "bot": "running"}


# -----------------------
# Webhook Setup
# -----------------------
async def setup_webhook():
    global telegram_app

    if telegram_app is None:
        raise RuntimeError("telegram_app not initialized")

    if not WEBHOOK_URL or not WEBHOOK_URL.startswith("https://"):
        raise RuntimeError("WEBHOOK_URL must start with https://")

    logger.info(f"Resetting webhook to: {WEBHOOK_URL}")

    await telegram_app.bot.delete_webhook(drop_pending_updates=True)
    await telegram_app.bot.set_webhook(url=WEBHOOK_URL)

    info = await telegram_app.bot.get_webhook_info()
    logger.info(f"Webhook is now set to: {info.url}")


async def remove_webhook():
    global telegram_app
    if telegram_app is None:
        return

    try:
        logger.info("Removing webhook...")
        await telegram_app.bot.delete_webhook()
    except Exception as e:
        logger.error(f"Failed removing webhook: {e}")


# -----------------------
# Event Loop Thread
# -----------------------
def _start_event_loop(loop: asyncio.AbstractEventLoop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


# -----------------------
# Main
# -----------------------
def main():
    global telegram_app, event_loop, loop_thread

    logger.info("Starting Telegram bot in webhook mode...")

    telegram_app = setup_application()

    event_loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(
        target=_start_event_loop, args=(event_loop,), daemon=True
    )
    loop_thread.start()

    # Initialize & start bot
    asyncio.run_coroutine_threadsafe(telegram_app.initialize(), event_loop).result()
    asyncio.run_coroutine_threadsafe(telegram_app.start(), event_loop).result()
    asyncio.run_coroutine_threadsafe(setup_webhook(), event_loop).result()

    logger.info(f"Starting Flask server on port {PORT}...")

    try:
        application.run(host="0.0.0.0", port=PORT, debug=False)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        if telegram_app and event_loop:
            asyncio.run_coroutine_threadsafe(remove_webhook(), event_loop).result()
            asyncio.run_coroutine_threadsafe(telegram_app.stop(), event_loop).result()
            asyncio.run_coroutine_threadsafe(telegram_app.shutdown(), event_loop).result()
            event_loop.call_soon_threadsafe(event_loop.stop)

        if loop_thread:
            loop_thread.join(timeout=5)


if __name__ == "__main__":
    main()