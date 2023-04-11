import html
import json
import logging
import traceback

from datetime import datetime

import chatgpt
import config
import database
import telegram

from settings import settings
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    User,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

# setup
db = database.Database()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

HELP_MESSAGE = """Commands:
⚪ /retry - Regenerate last bot answer
⚪ /new - Start new dialog
⚪ /mode - Select chat mode
⚪ /balance - Show balance
⚪ /my_api_key - Show user's oepnai api key
⚪ /set_api_key - Set user new openai api key
⚪ /help - Show help
"""

TELEGRAM_COMMANDS_MENUS = """
retry - Regenerate last bot answer
new - Start new dialog
mode - Select chat mode
balance - Show balance
my_api_key - Show user's oepnai api key
set_api_key - Set user new openai api key
help - Show help
"""


async def register_user_if_not_exists(update: Update, context: CallbackContext, user: User):
    if not db.check_if_user_exists(user.id):
        db.add_new_user(user.id, update.message.chat_id, username=user.username, first_name=user.first_name, last_name=user.last_name)
        db.start_new_dialog(user.id)

    if db.get_user_attribute(user.id, "current_dialog_id") is None:
        db.start_new_dialog(user.id)


async def start_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id

    db.set_user_attribute(user_id, "last_interaction", datetime.now())
    db.start_new_dialog(user_id)

    reply_text = "Hi! I'm <b>ChatGPT</b> bot implemented with GPT-3.5 OpenAI API 🤖\n\n"
    reply_text += HELP_MESSAGE

    reply_text += "\nAnd now... ask me anything!"

    await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML)


async def help_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())
    await update.message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.HTML)


async def retry_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    dialog_messages = db.get_dialog_messages(user_id, dialog_id=None)
    if len(dialog_messages) == 0:
        await update.message.reply_text("No message to retry 🤷‍♂️")
        return

    last_dialog_message = dialog_messages.pop()
    db.set_dialog_messages(user_id, dialog_messages, dialog_id=None) # last message was removed from the context

    await message_handle(update, context, message=last_dialog_message["user"], use_new_dialog_timeout=False)


async def message_handle(update: Update, context: CallbackContext, message=None, use_new_dialog_timeout=True):
    # check if message is edited
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return
    assert update.message
    assert update.message.from_user
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    openai_api_key: str | None = None
    try:
        openai_api_key = db.get_user_attribute(user_id, 'openai_api_key')
    except ValueError:
        pass

    # new dialog timeout
    if use_new_dialog_timeout:
        if (datetime.now() - db.get_user_attribute(user_id,
                                                   "last_interaction")).seconds > config.new_dialog_timeout and len(db.get_dialog_messages(user_id)) > 0:
            db.start_new_dialog(user_id)
            await update.message.reply_text("Starting new dialog due to timeout ✅")
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    # send typing action
    await update.message.chat.send_action(action="typing")

    try:
        message = message or update.message.text

        chatgpt_instance = chatgpt.ChatGPT(use_chatgpt_api=config.use_chatgpt_api)
        answer, n_used_tokens, n_first_dialog_messages_removed = chatgpt_instance.send_message(
            message,
            dialog_messages=db.get_dialog_messages(user_id, dialog_id=None),
            chat_mode=db.get_user_attribute(user_id, "current_chat_mode"),
            api_key = openai_api_key
        )

        # update user data
        new_dialog_message = {"user": message, "bot": answer, "date": datetime.now()}
        db.set_dialog_messages(user_id, db.get_dialog_messages(user_id, dialog_id=None) + [new_dialog_message], dialog_id=None)

        db.set_user_attribute(user_id, "n_used_tokens", n_used_tokens + db.get_user_attribute(user_id, "n_used_tokens"))

    except Exception as e:
        error_text = f"Something went wrong during completion. Reason: {e}"
        logger.error(error_text)
        await update.message.reply_text(error_text)
        return

    # send message if some messages were removed from the context
    if n_first_dialog_messages_removed > 0:
        if n_first_dialog_messages_removed == 1:
            text = "✍️ <i>Note:</i> Your current dialog is too long, so your <b>first message</b> was removed from the context.\n Send /new command to start new dialog"
        else:
            text = f"✍️ <i>Note:</i> Your current dialog is too long, so <b>{n_first_dialog_messages_removed} first messages</b> were removed from the context.\n Send /new command to start new dialog"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    try:
        await update.message.reply_text(answer, parse_mode=ParseMode.HTML)
    except telegram.error.BadRequest:
        # answer has invalid characters, so we send it without parse_mode
        await update.message.reply_text(answer)


async def new_dialog_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    db.start_new_dialog(user_id)
    await update.message.reply_text("Starting new dialog ✅")

    chat_mode = db.get_user_attribute(user_id, "current_chat_mode")
    await update.message.reply_text(f"{chatgpt.CHAT_MODES[chat_mode]['welcome_message']}", parse_mode=ParseMode.HTML)


async def show_chat_modes_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    keyboard = []
    for chat_mode, chat_mode_dict in chatgpt.CHAT_MODES.items():
        keyboard.append([InlineKeyboardButton(chat_mode_dict["name"], callback_data=f"set_chat_mode|{chat_mode}")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Select chat mode:", reply_markup=reply_markup)


async def set_chat_mode_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    user_id = update.callback_query.from_user.id

    query = update.callback_query
    await query.answer()

    chat_mode = query.data.split("|")[1]

    db.set_user_attribute(user_id, "current_chat_mode", chat_mode)
    db.start_new_dialog(user_id)

    await query.edit_message_text(f"<b>{chatgpt.CHAT_MODES[chat_mode]['name']}</b> chat mode is set", parse_mode=ParseMode.HTML)

    await query.edit_message_text(f"{chatgpt.CHAT_MODES[chat_mode]['welcome_message']}", parse_mode=ParseMode.HTML)


async def show_balance_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)

    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    n_used_tokens = db.get_user_attribute(user_id, "n_used_tokens")

    price = 0.002 if config.use_chatgpt_api else 0.02
    n_spent_dollars = n_used_tokens * (price/1000)

    text = f"You spent <b>{n_spent_dollars:.03f}$</b>\n"
    text += f"You used <b>{n_used_tokens}</b> tokens <i>(price: {price}$ per 1000 tokens)</i>\n"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def edited_message_handle(update: Update, context: CallbackContext):
    text = "🥲 Unfortunately, message <b>editing</b> is not supported"
    await update.edited_message.reply_text(text, parse_mode=ParseMode.HTML)


async def show_user_openai_api_key(update: Update, context: CallbackContext):
    assert update.message
    assert update.message.from_user
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    try:
        openai_api_key = db.get_user_attribute(user_id, 'openai_api_key')
        await update.message.reply_text(f"your openai api key: {openai_api_key}", parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text("api key not found.", parse_mode=ParseMode.HTML)


async def set_user_openai_api_key(update: Update, context: CallbackContext):
    assert update.message
    assert update.message.from_user

    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id

    if context.args:
        if len(context.args) > 1:
            await update.message.reply_text("too many arguments.", parse_mode=ParseMode.HTML)
        elif len(context.args) == 1:
            openai_api_key = context.args[0]
            db.set_user_attribute(user_id, 'openai_api_key', openai_api_key)
            await update.message.reply_text("set new openai api key success.", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("need openai api key.", parse_mode=ParseMode.HTML)


async def error_handle(update: Update, context: CallbackContext) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    try:
        # collect error message
        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        tb_string = "".join(tb_list)[:2000]
        update_str = update.to_dict() if isinstance(update, Update) else str(update)
        message = (
            f"An exception was raised while handling an update\n"
            f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
            "</pre>\n\n"
            f"<pre>{html.escape(tb_string)}</pre>"
        )

        # split text into multiple messages due to 4096 character limit
        message_chunk_size = 4000
        message_chunks = [message[i:i + message_chunk_size] for i in range(0, len(message), message_chunk_size)]
        for message_chunk in message_chunks:
            await context.bot.send_message(update.effective_chat.id, message_chunk, parse_mode=ParseMode.HTML)
    except:
        await context.bot.send_message(update.effective_chat.id, "Some error in error handler")


async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("/new",
                   "Start new dialog"),
        BotCommand("/mode",
                   "Select chat mode"),
        BotCommand("/retry",
                   "Re-generate response for previous query"),
        BotCommand("/balance",
                   "Show balance"),
        BotCommand("/set_api_key",
                   "Set your openai api key"),
        BotCommand("/my_api_key",
                   "Show your oepnai api key"),
        BotCommand("/help",
                   "Show help message"),
    ])


def run_bot() -> None:
    # todo: config log level
    logging.basicConfig(level=settings.log_level)
    application = (ApplicationBuilder().token(config.telegram_token).post_init(post_init).build())

    # add handlers
    if len(config.allowed_telegram_usernames) == 0:
        user_filter = filters.ALL
    else:
        user_filter = filters.User(username=config.allowed_telegram_usernames)

    application.add_handler(CommandHandler("start", start_handle, filters=user_filter))
    application.add_handler(CommandHandler("help", help_handle, filters=user_filter))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & user_filter, message_handle))
    application.add_handler(CommandHandler("retry", retry_handle, filters=user_filter))
    application.add_handler(CommandHandler("new", new_dialog_handle, filters=user_filter))

    application.add_handler(CommandHandler("mode", show_chat_modes_handle, filters=user_filter))
    application.add_handler(CallbackQueryHandler(set_chat_mode_handle, pattern="^set_chat_mode"))

    application.add_handler(CommandHandler("balance", show_balance_handle, filters=user_filter))
    application.add_handler(CommandHandler("my_api_key", show_user_openai_api_key, filters=user_filter))
    application.add_handler(CommandHandler("set_api_key", set_user_openai_api_key, filters=user_filter))

    application.add_error_handler(error_handle)

    # start the bot
    logger.info("start the bot")
    application.run_polling()


if __name__ == "__main__":
    run_bot()
