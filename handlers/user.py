import asyncio
import re
from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from database import (
    create_user,
    get_all_videos,
    get_user_by_telegram_id,
    get_video_by_title,
)

# States
NAME, PHONE, MENU = range(3)

ADMIN_BUTTONS = {"Add Video", "View Users", "Manage Videos"}


def _normalize_phone(text: str) -> str:
    t = text.strip()
    t = re.sub(r"[^\d+]", "", t)
    return t


def _build_videos_keyboard(titles: list[str]) -> ReplyKeyboardMarkup:
    rows: list[list[str]] = []
    row: list[str] = []
    for title in titles:
        row.append(title)
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    # Add a simple refresh button
    rows.append(["🔄 Refresh videos"])

    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


async def _send_video_menu(update: Update, prompt_text: str) -> None:
    if update.message is None:
        return

    videos = await asyncio.to_thread(get_all_videos)
    if not videos:
        await update.message.reply_text(
            "No videos available yet.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    titles = [video[1] for video in videos]
    reply_markup = _build_videos_keyboard(titles)
    await update.message.reply_text(prompt_text, reply_markup=reply_markup)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user is None or update.message is None:
        return ConversationHandler.END

    existing_user = await asyncio.to_thread(get_user_by_telegram_id, update.effective_user.id)
    if existing_user:
        await _send_video_menu(update, "Welcome back! Choose a video below.")
        return MENU

    await update.message.reply_text("Please enter your full name:")
    return NAME


async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or update.message.text is None:
        return NAME

    full_name = update.message.text.strip()
    if not full_name:
        await update.message.reply_text("Please enter your full name:")
        return NAME

    context.user_data["full_name"] = full_name

    reply_markup = ReplyKeyboardMarkup(
        [[KeyboardButton("Share phone number", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.message.reply_text(
        "Please share your phone number (press the button):",
        reply_markup=reply_markup,
    )
    return PHONE


async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Accepts either Telegram contact OR typed phone number.
    """
    if update.effective_user is None or update.message is None:
        return ConversationHandler.END

    name = str(context.user_data.get("full_name", "")).strip()
    if not name:
        await update.message.reply_text("Please enter your full name:")
        return NAME

    phone = ""
    if update.message.contact and update.message.contact.phone_number:
        phone = update.message.contact.phone_number.strip()
    else:
        phone = _normalize_phone((update.message.text or "").strip())

    digits_only = re.sub(r"\D", "", phone)
    if len(digits_only) < 7:
        await update.message.reply_text("Please share a valid phone number using the button.")
        return PHONE

    await asyncio.to_thread(create_user, update.effective_user.id, name, phone)
    context.user_data.pop("full_name", None)

    await _send_video_menu(update, "Registration successful! Choose a video below.")
    return MENU


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user is None or update.message is None:
        return MENU

    text = (update.message.text or "").strip()
    if not text:
        return MENU

    # Ignore admin panel button texts (prevents mixing)
    if text in ADMIN_BUTTONS:
        return MENU

    # Refresh
    if text == "🔄 Refresh videos":
        await _send_video_menu(update, "Updated list. Choose a video:")
        return MENU

    # Only respond if the text matches an actual video title
    video = await asyncio.to_thread(get_video_by_title, text)
    if not video:
        # Do nothing (no spam)
        return MENU

    await update.message.reply_text(f"Here is your video:\n{video[2]}")
    return MENU


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is not None:
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
    context.user_data.pop("full_name", None)
    return ConversationHandler.END


# One clean conversation for users
registration_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start_command)],
    states={
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name)],
        PHONE: [
            MessageHandler(filters.CONTACT, handle_phone),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone),
        ],
        MENU: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    block=True,
)