import asyncio
import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import ADMIN_ID
from database import (
    add_admin,
    create_video,
    delete_user_by_telegram_id,
    delete_video_by_id,
    get_all_users,
    get_all_videos_with_id,
    is_admin,
)

logger = logging.getLogger(__name__)

# Admin states
ADMIN_MENU, ADD_TITLE, ADD_LINK = range(3)


async def _is_admin(telegram_id: int) -> bool:
    if telegram_id == ADMIN_ID:
        return True
    return await asyncio.to_thread(is_admin, telegram_id)


# ---- Admin entry ----
async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user is None or update.message is None:
        return ConversationHandler.END

    if not await _is_admin(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return ConversationHandler.END

    # ✅ This prevents the USER menu handler from reacting after /admin
    context.user_data.clear()

    reply_markup = ReplyKeyboardMarkup(
        [["Add Video", "View Users"], ["Manage Videos"]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.message.reply_text("Admin panel:", reply_markup=reply_markup)
    return ADMIN_MENU


async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Access denied.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /addadmin <telegram_id>")
        return
    new_admin_id = int(context.args[0])
    await asyncio.to_thread(add_admin, new_admin_id)
    await update.message.reply_text(f"Added admin: {new_admin_id}")


# ---- Add video flow ----
async def add_video_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or update.effective_user is None:
        return ConversationHandler.END
    if not await _is_admin(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return ConversationHandler.END

    await update.message.reply_text("Enter video title:", reply_markup=ReplyKeyboardRemove())
    return ADD_TITLE


async def add_video_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or update.message.text is None:
        return ADD_TITLE
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text("Enter video title:")
        return ADD_TITLE
    context.user_data["video_title"] = title
    await update.message.reply_text("Enter YouTube link:")
    return ADD_LINK


async def add_video_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or update.message.text is None or update.effective_user is None:
        return ADD_LINK
    if not await _is_admin(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return ConversationHandler.END

    title = str(context.user_data.get("video_title", "")).strip()
    youtube_link = update.message.text.strip()
    if not title:
        return ADD_TITLE
    if not youtube_link:
        return ADD_LINK

    await asyncio.to_thread(create_video, title, youtube_link)
    context.user_data.pop("video_title", None)

    await update.message.reply_text("Video added successfully.")

    # Broadcast
    users = await asyncio.to_thread(get_all_users)
    broadcast_message = f"New video just released!\n{youtube_link}"

    for user in users:
        user_telegram_id = user[3]
        try:
            await context.bot.send_message(chat_id=user_telegram_id, text=broadcast_message)
        except Exception as e:
            logger.warning(f"Failed to send to {user_telegram_id}: {e}")
        await asyncio.sleep(0.05)

    # Back to admin menu
    reply_markup = ReplyKeyboardMarkup(
        [["Add Video", "View Users"], ["Manage Videos"]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.message.reply_text("Admin panel:", reply_markup=reply_markup)
    return ADMIN_MENU


# ---- View users ----
async def view_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user is None or update.message is None:
        return ADMIN_MENU
    if not await _is_admin(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return ADMIN_MENU

    users = await asyncio.to_thread(get_all_users)
    if not users:
        await update.message.reply_text("No registered users.")
        return ADMIN_MENU

    for user in users:
        _, name, phone, telegram_id = user
        text = f"Name: {name}\nPhone: {phone}\nTelegram ID: {telegram_id}"
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Delete", callback_data=f"delete_user_{telegram_id}")]]
        )
        await update.message.reply_text(text, reply_markup=reply_markup)

    return ADMIN_MENU


async def handle_delete_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.callback_query is None:
        return
    if not await _is_admin(update.effective_user.id):
        await update.callback_query.answer("Access denied.", show_alert=True)
        return
    data = update.callback_query.data or ""
    if not data.startswith("delete_user_"):
        return
    telegram_id_text = data.replace("delete_user_", "", 1)
    if not telegram_id_text.isdigit():
        return
    await asyncio.to_thread(delete_user_by_telegram_id, int(telegram_id_text))
    await update.callback_query.edit_message_text("User deleted successfully.")
    await update.callback_query.answer()


# ---- Manage videos ----
async def manage_videos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user is None or update.message is None:
        return ADMIN_MENU
    if not await _is_admin(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return ADMIN_MENU

    videos = await asyncio.to_thread(get_all_videos_with_id)
    if not videos:
        await update.message.reply_text("No videos available.")
        return ADMIN_MENU

    for video_id, title, youtube_link in videos:
        text = f"Title: {title}\nLink: {youtube_link}"
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Delete Video", callback_data=f"delete_video_{video_id}")]]
        )
        await update.message.reply_text(text, reply_markup=reply_markup)

    return ADMIN_MENU


async def handle_delete_video_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.callback_query is None:
        return
    if not await _is_admin(update.effective_user.id):
        await update.callback_query.answer("Access denied.", show_alert=True)
        return
    data = update.callback_query.data or ""
    if not data.startswith("delete_video_"):
        return
    video_id_text = data.replace("delete_video_", "", 1)
    if not video_id_text.isdigit():
        return
    await asyncio.to_thread(delete_video_by_id, int(video_id_text))
    await update.callback_query.edit_message_text("Video deleted successfully.")
    await update.callback_query.answer()


async def admin_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return ADMIN_MENU
    text = (update.message.text or "").strip()

    if text == "Add Video":
        return await add_video_start(update, context)
    if text == "View Users":
        return await view_users(update, context)
    if text == "Manage Videos":
        return await manage_videos(update, context)

    return ADMIN_MENU


async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is not None:
        await update.message.reply_text("Closed admin panel.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ✅ Admin conversation handler (this prevents overlap)
admin_conversation = ConversationHandler(
    entry_points=[CommandHandler("admin", admin_start)],
    states={
        ADMIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_menu_router)],
        ADD_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_video_title)],
        ADD_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_video_link)],
    },
    fallbacks=[CommandHandler("cancel", admin_cancel)],
    per_user=True,
    block=True,
)

addadmin_handler = CommandHandler("addadmin", addadmin_command)

admin_delete_user_callback_handler = CallbackQueryHandler(
    handle_delete_user_callback, pattern=r"^delete_user_\d+$", block=True
)
admin_delete_video_callback_handler = CallbackQueryHandler(
    handle_delete_video_callback, pattern=r"^delete_video_\d+$", block=True
)