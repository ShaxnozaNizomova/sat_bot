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
    create_video,
    delete_user_by_telegram_id,
    delete_video_by_id,
    get_all_users,
    get_all_videos_with_id,
    is_admin,
)

logger = logging.getLogger(__name__)

ADD_TITLE, ADD_LINK = range(2)


async def _is_admin(telegram_id: int) -> bool:
    # Super admin always allowed
    if telegram_id == ADMIN_ID:
        return True
    # Others must exist in DB admins table
    return await asyncio.to_thread(is_admin, telegram_id)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    if not await _is_admin(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return

    reply_markup = ReplyKeyboardMarkup(
        [["Add Video", "View Users"], ["Manage Videos"]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    await update.message.reply_text("Admin panel:", reply_markup=reply_markup)


async def cancel_admin_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is not None:
        await update.message.reply_text(
            "Cancelled.", reply_markup=ReplyKeyboardRemove()
        )
    context.user_data.pop("video_title", None)
    return ConversationHandler.END


async def add_video_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user is None or update.message is None:
        return ConversationHandler.END

    if not await _is_admin(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return ConversationHandler.END

    await update.message.reply_text("Enter video title:")
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
    if update.effective_user is None or update.message is None or update.message.text is None:
        return ADD_LINK

    if not await _is_admin(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return ConversationHandler.END

    title = str(context.user_data.get("video_title", "")).strip()
    youtube_link = update.message.text.strip()

    if not title or not youtube_link:
        return ADD_LINK

    await asyncio.to_thread(create_video, title, youtube_link)
    context.user_data.pop("video_title", None)

    await update.message.reply_text(
        "Video added successfully.",
        reply_markup=ReplyKeyboardRemove(),
    )

    users = await asyncio.to_thread(get_all_users)
    broadcast_message = f"New video just released!\n{youtube_link}"

    for user in users:
        user_telegram_id = user[3]
        try:
            await context.bot.send_message(
                chat_id=user_telegram_id,
                text=broadcast_message,
            )
        except Exception as e:
            logger.warning(f"Failed to send broadcast to {user_telegram_id}: {e}")
        await asyncio.sleep(0.05)

    return ConversationHandler.END


async def view_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    if not await _is_admin(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return

    users = await asyncio.to_thread(get_all_users)

    if not users:
        await update.message.reply_text("No registered users.")
        return

    for user in users:
        _, name, phone, telegram_id = user

        text = f"Name: {name}\nPhone: {phone}\nTelegram ID: {telegram_id}"

        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "❌ Delete",
                        callback_data=f"delete_user_{telegram_id}",
                    )
                ]
            ]
        )

        await update.message.reply_text(text, reply_markup=reply_markup)


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


async def manage_videos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    if not await _is_admin(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return

    videos = await asyncio.to_thread(get_all_videos_with_id)

    if not videos:
        await update.message.reply_text("No videos available.")
        return

    for video in videos:
        video_id, title, youtube_link = video

        text = f"Title: {title}\nLink: {youtube_link}"

        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "❌ Delete Video",
                        callback_data=f"delete_video_{video_id}",
                    )
                ]
            ]
        )

        await update.message.reply_text(text, reply_markup=reply_markup)


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


admin_add_video_handler = ConversationHandler(
    entry_points=[
        MessageHandler(filters.TEXT & filters.Regex(r"^Add Video$"), add_video_start)
    ],
    states={
        ADD_TITLE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, add_video_title)
        ],
        ADD_LINK: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, add_video_link)
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel_admin_flow)],
    block=True,
)

admin_view_users_handler = MessageHandler(
    filters.TEXT & filters.Regex(r"^View Users$"),
    view_users,
    block=True,
)

admin_manage_videos_handler = MessageHandler(
    filters.TEXT & filters.Regex(r"^Manage Videos$"),
    manage_videos,
    block=True,
)

admin_delete_user_callback_handler = CallbackQueryHandler(
    handle_delete_user_callback,
    pattern=r"^delete_user_\d+$",
    block=True,
)

admin_delete_video_callback_handler = CallbackQueryHandler(
    handle_delete_video_callback,
    pattern=r"^delete_video_\d+$",
    block=True,
)