import datetime
import importlib
import re
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import (
    Unauthorized,
    BadRequest,
    TimedOut,
    NetworkError,
    ChatMigrated,
    TelegramError,
)
from telegram.ext import CommandHandler, Filters, MessageHandler, CallbackQueryHandler
from telegram.ext.dispatcher import run_async, DispatcherHandlerStop, Dispatcher
from telegram.utils.helpers import escape_markdown

from tg_bot import (
    dispatcher,
    updater,
    CallbackContext,
    TOKEN,
    WEBHOOK,
    OWNER_ID,
    DONATION_LINK,
    CERT_PATH,
    PORT,
    URL,
    LOGGER,
    ALLOW_EXCL,
    INFO_START,
    INFO_HELP,
)

# needed to dynamically load modules
# NOTE: Module order is not guaranteed, specify that in the config file!
from tg_bot.modules import ALL_MODULES
from tg_bot.utils.chat_status import is_user_admin
from tg_bot.utils.misc import paginate_modules

START_STRING = """
Hello {username}! My name is <b>{botname}</b>, \
a group management bot to help you manage groups!
{info}
Hit /help if you want to know more about me!
""".format(
    username="{username}", botname="{botname}", info=INFO_START if INFO_START else ""
)

SOURCE_STRING = """
I'm built in python3, using the python-telegram-bot library, and am fully opensource - you can find what makes me tick [here](https://github.com/corsicanu/tgbot)
"""

HELP_STRING = """
<b>Help</b>

Hey there! My name is <b>{botname}</b>.
I am <b>a group management bot</b>, having a lot of useful features \
which may help you operate groups you are in!

<b>User commands:</b>
 - /start: Start me. You've probably already used this.
 - /help: Send this message.
   -> /help <code>&lt;module&gt;</code>: \
Send you info of the module.
{info}
All commands can be used with the following: <code>/</code> {cmd}
""".format(
    botname="{botname}",
    cmd="or <code>!</code>" if ALLOW_EXCL else "",
    info=INFO_HELP if INFO_HELP else "",
)

DONATE_STRING = """
You can send a donation to my current maintainers, @corsicanu and @nunopenim, via PayPal at paypal.me/corsicanu and/or paypal.me/nunopenim."""

IMPORTED = {}
MIGRATEABLE = []
HELPABLE = {}
STATS = []
USER_INFO = []
DATA_IMPORT = []
DATA_EXPORT = []

CHAT_SETTINGS = {}
USER_SETTINGS = {}

GDPR = []

for module_name in ALL_MODULES:
    imported_module = importlib.import_module("tg_bot.modules." + module_name)
    if not hasattr(imported_module, "__mod_name__"):
        imported_module.__mod_name__ = imported_module.__name__

    if not imported_module.__mod_name__.lower() in IMPORTED:
        IMPORTED[imported_module.__mod_name__.lower()] = imported_module
    else:
        raise Exception("Can't have two modules with the same name! Please change one")

    if hasattr(imported_module, "__help__") and imported_module.__help__:
        HELPABLE[imported_module.__mod_name__.lower()] = imported_module

    # Chats to migrate on chat_migrated events
    if hasattr(imported_module, "__migrate__"):
        MIGRATEABLE.append(imported_module)

    if hasattr(imported_module, "__stats__"):
        STATS.append(imported_module)

    if hasattr(imported_module, "__gdpr__"):
        GDPR.append(imported_module)

    if hasattr(imported_module, "__user_info__"):
        USER_INFO.append(imported_module)

    if hasattr(imported_module, "__import_data__"):
        DATA_IMPORT.append(imported_module)

    if hasattr(imported_module, "__export_data__"):
        DATA_EXPORT.append(imported_module)

    if hasattr(imported_module, "__chat_settings__"):
        CHAT_SETTINGS[imported_module.__mod_name__.lower()] = imported_module

    if hasattr(imported_module, "__user_settings__"):
        USER_SETTINGS[imported_module.__mod_name__.lower()] = imported_module


def send_help(
    text: str,
    chat: Update.effective_chat = None,
    query: Update.callback_query = None,
    keyboard: InlineKeyboardMarkup = None,
):
    bot = Dispatcher.bot

    # if Keyboard == "helpKB", use default help buttons markup.
    if keyboard == "helpKB":
        kb = paginate_modules(0, HELPABLE, "help")
        help_keyboard = InlineKeyboardMarkup(kb)
    # Else, use keyboard if it's not None.
    elif keyboard:
        help_keyboard = InlineKeyboardMarkup(keyboard)
    else:
        help_keyboard = None

    # Edit message when query is not None (Maybe callback?).
    if query:
        query.message.edit_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=help_keyboard,
            disable_web_page_preview=True,
        )
    elif chat:
        bot.send_message(
            chat_id=chat.id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=help_keyboard,
            disable_web_page_preview=True,
        )


def start(update: Update, context: CallbackContext):
    bot, args = context.bot, context.args
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]

    # Most of stuffs must require PM.
    if chat.type == "private":
        if len(args) >= 1:
            # If "help", send help pages.
            if args[0].lower()[:4] == "help":
                # If "help_<module_name>", send module help.
                if any(args[0].lower().replace("help_", "") == x for x in HELPABLE):
                    help_mod = HELPABLE[args[0].lower().replace("help_", "")]
                    text = f"<b>{help_mod.__mod_name__}</b>\n{help_mod.__help__}"

                    # Append keyboard from __help_kb__ & add help_back keyboard.
                    if hasattr(help_mod, "__help_kb__"):
                        keyboard = help_mod.__help_kb__.copy()
                        keyboard.append(
                            [
                                InlineKeyboardButton(
                                    text="Back", callback_data="help_back"
                                )
                            ]
                        )
                    else:
                        keyboard = [
                            [
                                InlineKeyboardButton(
                                    text="Back", callback_data="help_back"
                                )
                            ]
                        ]

                    send_help(
                        text,
                        chat=chat,
                        keyboard=keyboard,
                    )

                else:
                    send_help(
                        HELP_STRING.format(botname=bot.first_name),
                        chat=chat,
                        keyboard="helpKB",
                    )

                return

            # Send rules.
            if args[0][1:].isdecimal() and "rules" in IMPORTED:
                IMPORTED["rules"].send_rules(update, args[0], from_pm=True)
                return

        # Send start.
        text = START_STRING.format(
            username=user.first_name,
            botname=bot.first_name,
        )
        keyboard = [
            InlineKeyboardButton(
                text="Add me to your group!",
                url="t.me/{}?startgroup=true".format(bot.username),
            )
        ]

        msg.reply_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([keyboard]),
            disable_web_page_preview=True,
        )

        return

    # Send the bot is alive.
    msg.reply_text("Hey there, I'm alive!")


# for test purposes
def error_callback(update, context):
    bot = context.bot
    error = context.error
    try:
        raise error
    except Unauthorized:
        print("no nono1")
        print(error)
        # remove update.message.chat_id from conversation list
    except BadRequest:
        print("no nono2")
        print("BadRequest caught")
        print(error)

        # handle malformed requests - read more below!
    except TimedOut:
        print("no nono3")
        # handle slow connection problems
    except NetworkError:
        print("no nono4")
        # handle other connection problems
    except ChatMigrated as err:
        print("no nono5")
        print(err)
        # the chat_id of a group has changed, use e.new_chat_id instead
    except TelegramError:
        print(error)
        # handle all other telegram related errors


def help_button(update: Update, context: CallbackContext):
    bot = context.bot
    query = update.callback_query

    mod_match = re.match(r"help_module\((.+?)\)", query.data)
    prev_match = re.match(r"help_prev\((.+?)\)", query.data)
    next_match = re.match(r"help_next\((.+?)\)", query.data)
    back_match = re.match(r"help_back", query.data)

    try:
        if mod_match:
            module = mod_match.group(1)
            help_mod = HELPABLE[module]
            # Add module name in front of module help.
            help_text = f"<b>{help_mod.__mod_name__}</b>\n{help_mod.__help__}"

            # Append keyboard from __help_kb__ & add help_back keyboard.
            if hasattr(help_mod, "__help_kb__"):
                keyboard = help_mod.__help_kb__.copy()
                keyboard.append(
                    [InlineKeyboardButton(text="Back", callback_data="help_back")]
                )
            else:
                keyboard = [
                    [InlineKeyboardButton(text="Back", callback_data="help_back")]
                ]

            send_help(help_text, query=query, keyboard=keyboard)

        if prev_match:
            page = int(prev_match.group(1))
            help_text = HELP_STRING.format(botname=bot.first_name)
            keyboard = paginate_modules(page - 1, HELPABLE, "help")

            send_help(help_text, query=query, keyboard=[keyboard])

        if next_match:
            page = int(next_match.group(1))
            help_text = HELP_STRING.format(botname=bot.first_name)
            keyboard = paginate_modules(page + 1, HELPABLE, "help")

            send_help(help_text, query=query, keyboard=[keyboard])

        if back_match:
            help_text = HELP_STRING.format(botname=bot.first_name)
            send_help(help_text, query=query, keyboard="helpKB")

        # Ensure not to make a spin.
        bot.answer_callback_query(query.id)

    except BadRequest as excp:
        if excp.message in ("Message is not modified", "Query_id_invalid"):
            pass
        else:
            LOGGER.exception("Exception in help buttons. %s", str(query.data))


def get_help(update: Update, context: CallbackContext):
    bot = context.bot
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]
    args = update.effective_message.text.split(None, 1)

    # Send help strings only in PM.
    if chat.type != chat.PRIVATE:
        if len(args) >= 2 and any(args[1].lower() == x for x in HELPABLE):
            module = f"{args[1].lower()}"
        else:
            module = ""
        text = "Contact me in PM for help."
        url = f"t.me/{bot.username}?start=help_{module}"
        keyboard = [InlineKeyboardButton(text="Help", url=url)]

        msg.reply_text(text=text, reply_markup=InlineKeyboardMarkup([keyboard]))
        return

    # Send module help.
    if len(args) >= 2 and any(args[1].lower() == x for x in HELPABLE):
        help_mod = HELPABLE[args[1].lower()]
        text = f"<b>{help_mod.__mod_name__}</b>\n{help_mod.__help__}"

        # Append keyboard from __help_kb__ & add help_back keyboard.
        if hasattr(help_mod, "__help_kb__"):
            keyboard = help_mod.__help_kb__.copy()
            keyboard.append(
                [InlineKeyboardButton(text="Back", callback_data="help_back")]
            )
        else:
            keyboard = [[InlineKeyboardButton(text="Back", callback_data="help_back")]]

        send_help(
            text,
            chat=chat,
            keyboard=keyboard,
        )

    # Send help.
    else:
        send_help(
            HELP_STRING.format(botname=bot.first_name), chat=chat, keyboard="helpKB"
        )


def send_settings(chat_id, user_id, user=False):
    if user:
        if USER_SETTINGS:
            settings = "\n\n".join(
                "*{}*:\n{}".format(mod.__mod_name__, mod.__user_settings__(user_id))
                for mod in USER_SETTINGS.values()
            )
            dispatcher.bot.send_message(
                user_id,
                "These are your current settings:" + "\n\n" + settings,
                parse_mode=ParseMode.MARKDOWN,
            )

        else:
            dispatcher.bot.send_message(
                user_id,
                "Seems like there aren't any user specific settings available :'(",
                parse_mode=ParseMode.MARKDOWN,
            )

    else:
        if CHAT_SETTINGS:
            chat_name = dispatcher.bot.getChat(chat_id).title
            dispatcher.bot.send_message(
                user_id,
                text="Which module would you like to check {}'s settings for?".format(
                    chat_name
                ),
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(0, CHAT_SETTINGS, "stngs", chat=chat_id)
                ),
            )
        else:
            dispatcher.bot.send_message(
                user_id,
                "Seems like there aren't any chat settings available :'(\nSend this "
                "in a group chat you're admin in to find its current settings!",
                parse_mode=ParseMode.MARKDOWN,
            )


def settings_button(update: Update, context: CallbackContext):
    bot = context.bot
    query = update.callback_query
    user = update.effective_user
    mod_match = re.match(r"stngs_module\((.+?),(.+?)\)", query.data)
    prev_match = re.match(r"stngs_prev\((.+?),(.+?)\)", query.data)
    next_match = re.match(r"stngs_next\((.+?),(.+?)\)", query.data)
    back_match = re.match(r"stngs_back\((.+?)\)", query.data)
    try:
        if mod_match:
            chat_id = mod_match.group(1)
            module = mod_match.group(2)
            chat = bot.get_chat(chat_id)
            text = "*{}* has the following settings for the *{}* module:\n\n".format(
                escape_markdown(chat.title), CHAT_SETTINGS[module].__mod_name__
            ) + CHAT_SETTINGS[module].__chat_settings__(chat_id, user.id)
            query.message.edit_text(
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="Back",
                                callback_data="stngs_back({})".format(chat_id),
                            )
                        ]
                    ]
                ),
            )

        elif prev_match:
            chat_id = prev_match.group(1)
            curr_page = int(prev_match.group(2))
            chat = bot.get_chat(chat_id)
            query.message.edit_text(
                "Hi there! There are quite a few settings for {} - go ahead and pick what "
                "you're interested in.".format(chat.title),
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(
                        curr_page - 1, CHAT_SETTINGS, "stngs", chat=chat_id
                    )
                ),
            )

        elif next_match:
            chat_id = next_match.group(1)
            next_page = int(next_match.group(2))
            chat = bot.get_chat(chat_id)
            query.message.edit_text(
                "Hi there! There are quite a few settings for {} - go ahead and pick what "
                "you're interested in.".format(chat.title),
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(
                        next_page + 1, CHAT_SETTINGS, "stngs", chat=chat_id
                    )
                ),
            )

        elif back_match:
            chat_id = back_match.group(1)
            chat = bot.get_chat(chat_id)
            query.message.edit_text(
                text="Hi there! There are quite a few settings for {} - go ahead and pick what "
                "you're interested in.".format(escape_markdown(chat.title)),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(0, CHAT_SETTINGS, "stngs", chat=chat_id)
                ),
            )

        # ensure no spinny white circle
        bot.answer_callback_query(query.id)
    except BadRequest as excp:
        if excp.message == "Message is not modified":
            pass
        elif excp.message == "Query_id_invalid":
            pass
        elif excp.message == "Message can't be deleted":
            pass
        else:
            LOGGER.exception("Exception in settings buttons. %s", str(query.data))


def get_settings(update: Update, context: CallbackContext):
    bot = context.bot
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]
    args = msg.text.split(None, 1)

    # ONLY send settings in PM
    if chat.type != chat.PRIVATE:
        if is_user_admin(chat, user.id):
            text = "Click here to get this chat's settings, as well as yours."
            msg.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="Settings",
                                url="t.me/{}?start=stngs_{}".format(
                                    bot.username, chat.id
                                ),
                            )
                        ]
                    ]
                ),
            )
        else:
            text = "Click here to check your settings."

    else:
        send_settings(chat.id, user.id, True)


def donate(update: Update, context: CallbackContext):
    bot = context.bot
    user = update.effective_message.from_user
    chat = update.effective_chat  # type: Optional[Chat]

    if chat.type == "private":
        update.effective_message.reply_text(
            DONATE_STRING, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
        )

        update.effective_message.reply_text(
            "You can also donate to my creator, SonOfLars, for all his work to get me where i am now. There are two ways of paying him: [PayPal](paypal.me/PaulSonOfLars), or [Monzo](monzo.me/paulnionvestergaardlarsen).",
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )

    else:
        try:
            bot.send_message(
                user.id,
                DONATE_STRING,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )

            update.effective_message.reply_text(
                "I've PM'ed you about donating to my owner!"
            )
        except Unauthorized:
            update.effective_message.reply_text(
                "Contact me in PM first to get donation information."
            )


def source(update: Update, context: CallbackContext):
    bot = context.bot
    user = update.effective_message.from_user
    chat = update.effective_chat  # type: Optional[Chat]

    if chat.type == "private":
        update.effective_message.reply_text(
            SOURCE_STRING, parse_mode=ParseMode.MARKDOWN
        )

    else:
        try:
            bot.send_message(user.id, SOURCE_STRING, parse_mode=ParseMode.MARKDOWN)

            update.effective_message.reply_text(
                "You'll find in PM more info about my sourcecode."
            )
        except Unauthorized:
            update.effective_message.reply_text(
                "Contact me in PM first to get source information."
            )


def migrate_chats(update: Update, context: CallbackContext):
    bot = context.bot
    msg = update.effective_message  # type: Optional[Message]
    if msg.migrate_to_chat_id:
        old_chat = update.effective_chat.id
        new_chat = msg.migrate_to_chat_id
    elif msg.migrate_from_chat_id:
        old_chat = msg.migrate_from_chat_id
        new_chat = update.effective_chat.id
    else:
        return

    LOGGER.info("Migrating from %s, to %s", str(old_chat), str(new_chat))
    for mod in MIGRATEABLE:
        mod.__migrate__(old_chat, new_chat)

    LOGGER.info("Successfully migrated!")
    raise DispatcherHandlerStop


def regexhelp(update: Update, context: CallbackContext):
    rstring = """
The only supported regex character for blacklist/filter/warnfilter triggers is `"*"`(asterisk)

Check the following examples:
`/addblacklist a*bc`

This will trigger blacklist on cases like:
• `abc`
• `a*bc`
• `a<some character>bc`
• `a<some random text(no line breaks)>bc`

`/addblacklist a\*bc`

This will trigger blacklist on `a*bc` only.

*Note:* This applies to blacklist/filter/warnfilter.
"""
    update.effective_message.reply_text(rstring, parse_mode=ParseMode.MARKDOWN)


def main():
    start_handler = CommandHandler("start", start, run_async=True)

    help_handler = CommandHandler("help", get_help, run_async=True)
    help_callback_handler = CallbackQueryHandler(
        help_button, pattern=r"help_", run_async=True
    )

    settings_handler = CommandHandler("settings", get_settings, run_async=True)
    settings_callback_handler = CallbackQueryHandler(
        settings_button, pattern=r"stngs_", run_async=True
    )

    donate_handler = CommandHandler("donate", donate, run_async=True)
    source_handler = CommandHandler("source", source, run_async=True)
    migrate_handler = MessageHandler(Filters.status_update.migrate, migrate_chats)

    rhelp_handler = CommandHandler(
        "regexhelp", regexhelp, filters=Filters.private, run_async=True
    )

    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(help_handler)
    dispatcher.add_handler(source_handler)
    dispatcher.add_handler(settings_handler)
    dispatcher.add_handler(help_callback_handler)
    dispatcher.add_handler(settings_callback_handler)
    dispatcher.add_handler(migrate_handler)
    dispatcher.add_handler(donate_handler)
    dispatcher.add_handler(rhelp_handler)

    # dispatcher.add_error_handler(error_callback)

    # add antiflood processor
    Dispatcher.process_update = process_update

    if WEBHOOK:
        LOGGER.info("Using webhooks.")
        updater.start_webhook(listen="127.0.0.1", port=PORT, url_path=TOKEN)

        if CERT_PATH:
            updater.bot.set_webhook(url=URL + TOKEN, certificate=open(CERT_PATH, "rb"))
        else:
            updater.bot.set_webhook(url=URL + TOKEN)

    else:
        LOGGER.info("Using long polling.")
        updater.start_polling(timeout=15, read_latency=4)

    updater.idle()


CHATS_CNT = {}
CHATS_TIME = {}


def process_update(self, update):
    # An error happened while polling
    if isinstance(update, TelegramError):
        try:
            self.dispatch_error(None, update)
        except Exception:
            self.logger.exception(
                "An uncaught error was raised while handling the error"
            )
        return

    now = datetime.datetime.utcnow()
    updatedChat = update.effective_chat
    if hasattr(updatedChat, "id"):
        cnt = CHATS_CNT.get(updatedChat.id, 0)
        t = CHATS_TIME.get(updatedChat.id, datetime.datetime(1970, 1, 1))
    else:  # investigating new nonetype error solutions
        return  # halting process if NoneType object is encountered

    if t and now > t + datetime.timedelta(0, 1):
        CHATS_TIME[update.effective_chat.id] = now
        cnt = 0
    else:
        cnt += 1

    if cnt > 10:
        return

    CHATS_CNT[update.effective_chat.id] = cnt
    for group in self.groups:
        try:
            for handler in (x for x in self.handlers[group] if x.check_update(update)):
                check = handler.check_update(update)
                context = CallbackContext.from_update(update, self)
                handler.handle_update(update, self, check, context)
                break

        # Stop processing with any other handler.
        except DispatcherHandlerStop:
            self.logger.debug("Stopping further handlers due to DispatcherHandlerStop")
            break

        # Dispatch any error.
        except TelegramError as te:
            self.logger.warning(
                "A TelegramError was raised while processing the Update"
            )

            try:
                self.dispatch_error(update, te)
            except DispatcherHandlerStop:
                self.logger.debug("Error handler stopped further handlers")
                break
            except Exception:
                self.logger.exception(
                    "An uncaught error was raised while handling the error"
                )

        # Errors should not stop the thread.
        except Exception:
            self.logger.exception(
                "An uncaught error was raised while processing the update"
            )


if __name__ == "__main__":
    LOGGER.info("Successfully loaded modules: " + str(ALL_MODULES))
    main()
